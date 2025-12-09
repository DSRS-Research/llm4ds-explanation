#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Convert a JSONL LLM-generation file into Markdown files.
Each case becomes:
    md_out/case_<case_id>.md

Contents:
    # Case <ID>
    ## Explanation
    <text>

    ## Refactoring Plan
    <text>

    ## Meta Validation
    <text>
"""

import json
from pathlib import Path

# Input path: update if needed
GEN_PATH = Path("data/generations/llama3.1:8b_ollama.jsonl")

# Output folder
OUT_DIR = Path("md_out")
OUT_DIR.mkdir(exist_ok=True)


def clean_filename(text: str) -> str:
    # keep letters, numbers, dash, underscore
    return "".join(c for c in text if c.isalnum() or c in "-_").strip("_")


def main():
    if not GEN_PATH.exists():
        raise SystemExit(f"File not found: {GEN_PATH}")

    index_entries = []

    with GEN_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            rec = json.loads(line)

            case_id = rec.get("case_id", "unknown")
            safe_id = clean_filename(str(case_id))

            explain = rec.get("explain", {}).get("text", "")
            refactor = rec.get("refactor", {}).get("text", "")
            meta = rec.get("meta_validation", {}).get("text", "")

            md_text = f"""# Case {case_id}

## Explanation
{explain}

## Refactoring Plan
{refactor}

## Meta Validation
{meta}
"""

            out_path = OUT_DIR / f"case_{safe_id}.md"
            out_path.write_text(md_text, encoding="utf-8")

            index_entries.append(f"- [Case {case_id}](case_{safe_id}.md)")

    # Optional: write summary index file
    (OUT_DIR / "INDEX.md").write_text(
        "# Index of Cases\n\n" + "\n".join(index_entries),
        encoding="utf-8",
    )

    print(f"Done. Markdown files saved in: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
