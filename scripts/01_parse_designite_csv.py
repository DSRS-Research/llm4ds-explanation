#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse DesigniteJava class-level smells CSV (or pasted TSV) into a clean table.
Expected columns (case-insensitive, flexible spacing):
  Project Name | Package Name | Type Name | Design Smell | Cause of the Smell
Outputs:
  data/interim/smells.parquet
  data/interim/smells.csv
"""
import argparse, hashlib, json, os, re, sys
from pathlib import Path
import pandas as pd

COLMAP = {
    "project name": "project",
    "package name": "package",
    "type name": "class_name",
    "design smell": "smell_type",
    "cause of the smell": "detector_reason",
}

def smart_read_table(path: Path) -> pd.DataFrame:
    # Try CSV then TSV then Excel
    try:
        df = pd.read_csv(path, dtype=str, engine="python")
        if df.shape[1] == 1:
            raise ValueError("single column CSV—likely TSV")
        return df
    except Exception:
        try:
            df = pd.read_csv(path, sep="\t", dtype=str, engine="python")
            return df
        except Exception:
            return pd.read_excel(path, dtype=str)

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.strip().lower(): c for c in df.columns}
    rename = {}
    for k,v in COLMAP.items():
        if k in cols:
            rename[cols[k]] = v
    out = df.rename(columns=rename)
    missing = [v for v in COLMAP.values() if v not in out.columns]
    if missing:
        raise SystemExit(f"Missing expected columns: {missing}. Got: {list(df.columns)}")
    # Trim whitespace
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].astype(str).str.strip()
    return out[list(COLMAP.values())]

METRIC_PATTERNS = {
    "WMC": r"\bWMC\s*\(?([0-9]+)\)?",
    "CBO": r"\bCBO\s*\(?([0-9]+)\)?",
    "RFC": r"\bRFC\s*\(?([0-9]+)\)?",
    "LCOM": r"\bLCOM\s*\(?([0-9]*\.?[0-9]+)\)?",
    "LOC": r"\bLOC\s*\(?([0-9]+)\)?",
    "NMD": r"\bNMD\s*\(?([0-9]+)\)?",
    "NAD": r"\bNAD\s*\(?([0-9]+)\)?",
}

def extract_metrics(text: str) -> dict:
    m = {}
    if not isinstance(text, str): 
        return m
    for k, pat in METRIC_PATTERNS.items():
        r = re.search(pat, text)
        if r:
            try:
                m[k] = float(r.group(1)) if "." in r.group(1) else int(r.group(1))
            except Exception:
                pass
    return m

def make_case_id(row) -> str:
    h = hashlib.sha1(f"{row['project']}|{row['package']}|{row['class_name']}|{row['smell_type']}|{row['detector_reason']}".encode()).hexdigest()[:12]
    return f"{row['project'].replace(' ','_')}_{h}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to DesigniteJava smell CSV/TSV/XLSX")
    ap.add_argument("--outdir", default="data/interim", help="Output directory")
    args = ap.parse_args()

    inp = Path(args.input)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    df = smart_read_table(inp)
    df = normalize_columns(df)

    # metrics JSON
    df["metrics"] = df["detector_reason"].apply(extract_metrics).apply(json.dumps)
    df["case_id"] = df.apply(make_case_id, axis=1)

    # Preserve inner-class names; also compute outer type for file resolution
    def split_inner(name: str):
        return (name.split(".")[0], name if "." in name else None)
    df[["outer_class","inner_class"]] = df["class_name"].apply(lambda s: pd.Series(split_inner(s)))

    # Save
    df.to_csv(outdir / "smells.csv", index=False)
    try:
        df.to_parquet(outdir / "smells.parquet", index=False)
    except Exception:
        pass

    print(f"Saved {len(df)} rows to {outdir}")
    print(df.head(3).to_string(index=False))

if __name__ == "__main__":
    main()
