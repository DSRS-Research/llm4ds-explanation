#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build LLM-ready cases by resolving Java source files from package + class, then extracting a focused code excerpt.
Inputs:
  data/interim/smells.csv (from parse_designite_csv.py)
  --repo_dir path to K-9 source root (contains app/src/...)
Outputs:
  data/cases/cases.jsonl
Strategy:
  - Resolve file: package -> path, outer_class -> <Outer>.java
  - If inner class present (A.B), search for 'class B' region inside the file to focus excerpt.
  - Heuristics by smell type to select relevant lines (public fields for Deficient Encapsulation, etc.).
"""
import argparse, json, os, re
from pathlib import Path
import pandas as pd

def find_java_file(repo_dir: Path, package: str, outer_class: str) -> Path | None:
    rel = Path(*package.split(".")) / f"{outer_class}.java"
    candidates = list(repo_dir.rglob(str(rel)))
    return candidates[0] if candidates else None

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return p.read_text(encoding="latin-1")

def slice_inner_class(text: str, inner: str | None) -> str:
    if not inner or inner == "":
        return text
    # inner might be A.B.C; take last
    inner_name = inner.split(".")[-1]
    pat = re.compile(rf"\b(class|interface|enum)\s+{re.escape(inner_name)}\b[\s\S]*?\n\}}", re.M)
    m = pat.search(text)
    return m.group(0) if m else text

def heuristic_excerpt(text: str, smell: str, loc_limit: int = 400) -> str:
    lines = text.splitlines()
    if smell.lower().startswith("deficient encapsulation"):
        sel = [i for i,l in enumerate(lines) if re.search(r"\bpublic\s+(static\s+)?(final\s+)?[\w\<\>\[\]]+\s+\w+\s*(=|;)", l)]
        window = []
        for idx in sel:
            window.extend(range(max(0,idx-3), min(len(lines), idx+4)))
        window = sorted(set(window))
        chosen = [lines[i] for i in window]
    elif smell.lower().startswith("unnecessary abstraction") or smell.lower().startswith("unutilized abstraction"):
        # show class header + fields (no methods)
        header_idx = next((i for i,l in enumerate(lines) if re.search(r"\b(class|interface|enum)\b", l)), 0)
        fields = [l for l in lines if re.search(r"\b(private|protected|public)\s+(static\s+)?(final\s+)?[\w\<\>\[\]]+\s+\w+\s*(=|;)", l)]
        chosen = lines[header_idx:header_idx+30] + fields[:40]
    else:
        # fallback: take first class block up to limit
        chosen = lines[:loc_limit]
    # truncate
    out = chosen[:loc_limit]
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smells_csv", default="data/interim/smells.csv")
    ap.add_argument("--metrics_csv", default=None)
    ap.add_argument("--repo_dir", required=True)
    ap.add_argument("--out", default="data/cases/cases.jsonl")
    ap.add_argument("--loc_limit", type=int, default=400)
    args = ap.parse_args()

    df = pd.read_csv(args.smells_csv, dtype=str)
    metrics_df = None
    if args.metrics_csv:
        try:
            metrics_df = pd.read_csv(args.metrics_csv, dtype=str)
        except Exception:
            pass
    repo_dir = Path(args.repo_dir)

    out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    with open(out_path, "w", encoding="utf-8") as fout:
        for _, r in df.iterrows():
            java_path = find_java_file(repo_dir, r["package"], r["outer_class"])
            if not java_path or not java_path.exists():
                continue
            code = read_text(java_path)
            code = slice_inner_class(code, r.get("inner_class"))
            excerpt = heuristic_excerpt(code, r["smell_type"], args.loc_limit)
            # attach metrics if available (either via merged smells CSV or separate metrics file)
            metrics_payload = r.get("metrics","{}")
            try:
                import json as _json
                _m = _json.loads(metrics_payload) if isinstance(metrics_payload, str) else metrics_payload
            except Exception:
                _m = {}
            # If separate metrics CSV is supplied and has matching row (by class/package/project), add columns
            if metrics_df is not None:
                try:
                    key_cols = ["project","package","class_name"]
                    # ensure we have canonical names in df
                    if all(k in df.columns for k in key_cols):
                        sub = metrics_df
                        # try to align columns names
                        cols = {c.lower(): c for c in metrics_df.columns}
                        pn = cols.get("project name", None)
                        pk = cols.get("package name", None)
                        tn = cols.get("type name", None)
                        if pn and pk and tn:
                            rowm = metrics_df[(metrics_df[pn]==r["project"]) & (metrics_df[pk]==r["package"]) & (metrics_df[tn]==r["class_name"])].head(1)
                            if len(rowm)==1:
                                _m.update({k: rowm.iloc[0][k] for k in rowm.columns if k not in (pn,pk,tn)})
                except Exception:
                    pass
            obj = {
                "case_id": r["case_id"],
                "project": r["project"],
                "file_path": str(java_path),
                "package": r["package"],
                "class_name": r["class_name"],
                "smell_type": r["smell_type"],
                "detector_reason": r["detector_reason"],
                "metrics": _m,
                "code_excerpt": excerpt,
                "excerpt_strategy": "heuristic_by_smell",
            }
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n_written += 1
    print(f"Wrote {n_written} cases to {out_path}")

if __name__ == "__main__":
    main()
