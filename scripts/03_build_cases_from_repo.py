#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Improved builder:
- Uses Designite's 'Line no' to locate the precise smell position.
- Extracts the full class or inner-class block using brace matching.
- Falls back to a window if something goes wrong.
- No more smell-specific heuristics needed for excerpt.

Input:
  smells.csv (must contain: project, package, class_name, outer_class, inner_class, smell_type, detector_reason, Line no)
  --repo_dir /path/to/K-9

Output:
  cases.jsonl (LLM-ready)
"""

import argparse, json, re
from pathlib import Path
import pandas as pd


# --------------------------------------------------------------------
# File resolution
# --------------------------------------------------------------------
def find_java_file(repo_dir: Path, package: str, outer_class: str) -> Path | None:
    rel_path = Path(*package.split(".")) / f"{outer_class}.java"
    candidates = list(repo_dir.rglob(str(rel_path)))
    return candidates[0] if candidates else None


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return p.read_text(encoding="latin-1")


# --------------------------------------------------------------------
# Class block extractor (inner or outer class)
# --------------------------------------------------------------------
def extract_class_block(text: str, start_line: int, class_name: str, loc_limit: int = 400) -> str:
    """
    Extracts the entire inner class (or outer class) containing the smell
    by:
      - locating the class header near the Designite-reported line
      - brace-matching until the class ends
    """
    lines = text.splitlines()
    n = len(lines)
    if start_line < 1 or start_line > n:
        return "\n".join(lines[:loc_limit])

    start_idx = start_line - 1      # convert to 0-based
    simple_name = class_name.split(".")[-1]

    # Search nearby for class header: class|interface|enum <simple_name>
    header_pat = re.compile(rf"\b(class|interface|enum)\s+{re.escape(simple_name)}\b")
    header_idx = None

    # Search from start_idx upward slightly and downward
    search_range = range(max(0, start_idx - 5), min(n, start_idx + 10))
    for i in search_range:
        if header_pat.search(lines[i]):
            header_idx = i
            break

    # If still not found, scan the whole file (rare)
    if header_idx is None:
        for i, line in enumerate(lines):
            if header_pat.search(line):
                header_idx = i
                break

    if header_idx is None:
        # Cannot find header → fallback to window
        lo = max(0, start_idx - 5)
        hi = min(n, lo + loc_limit)
        return "\n".join(lines[lo:hi])

    # ----------------------------------------------------------------
    # Brace-match to find class block end
    # ----------------------------------------------------------------
    depth = 0
    opened = False
    end_idx = None

    # Concatenate lines starting at header_idx
    for rel_line_idx in range(header_idx, n):
        line = lines[rel_line_idx]
        for ch in line:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
                if opened and depth == 0:
                    end_idx = rel_line_idx
                    break
        if end_idx is not None:
            break

    # If class end not found → fallback
    if end_idx is None:
        lo = max(0, header_idx)
        hi = min(n, lo + loc_limit)
        return "\n".join(lines[lo:hi])

    lo = max(0, header_idx)
    hi = end_idx + 1
    excerpt_lines = lines[lo:hi]

    # Enforce loc_limit
    if len(excerpt_lines) > loc_limit:
        excerpt_lines = excerpt_lines[:loc_limit]

    return "\n".join(excerpt_lines)


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smells_csv", default="data/interim/smells.csv")
    ap.add_argument("--repo_dir", required=True)
    ap.add_argument("--out", default="data/cases/cases.jsonl")
    ap.add_argument("--loc_limit", type=int, default=400)
    args = ap.parse_args()

    df = pd.read_csv(args.smells_csv, dtype=str)
    repo_dir = Path(args.repo_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_written = 0

    with out_path.open("w", encoding="utf-8") as fout:
        for _, r in df.iterrows():

            if "Line no" not in r or not str(r["Line no"]).isdigit():
                continue

            start_line = int(r["Line no"])
            java_path = find_java_file(repo_dir, r["package"], r["outer_class"])
            if not java_path or not java_path.exists():
                continue

            code = read_text(java_path)
            excerpt = extract_class_block(
                text=code,
                start_line=start_line,
                class_name=r["class_name"],
                loc_limit=args.loc_limit
            )

            # Build metrics dictionary (already normalized by your pipeline)
            try:
                metrics = json.loads(r.get("metrics", "{}"))
            except Exception:
                metrics = {}

            obj = {
                "case_id": r["case_id"],
                "project": r["project"],
                "file_path": str(java_path),
                "package": r["package"],
                "class_name": r["class_name"],
                "smell_type": r["smell_type"],
                "detector_reason": r["detector_reason"],
                "metrics": metrics,
                "code_excerpt": excerpt,
                "excerpt_strategy": "line_based_class_block"
            }

            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n_written += 1

    print(f"Wrote {n_written} cases → {out_path}")


if __name__ == "__main__":
    main()