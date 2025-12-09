#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge Designite metrics with smell detections.
Inputs:
  data/interim/smells.csv         (from parse_designite_csv.py)
  --metrics_csv path/to/metrics.csv  (Designite metrics export; CSV/TSV/XLSX)
Outputs:
  data/interim/smells_with_metrics.csv
  data/interim/smells_with_metrics.parquet (best-effort)
"""
import argparse
import pandas as pd
from pathlib import Path

def smart_read_table(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str, engine="python")
    except Exception:
        try:
            return pd.read_csv(path, sep="\t", dtype=str, engine="python")
        except Exception:
            return pd.read_excel(path, dtype=str)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smells_csv", default="data/interim/smells.csv")
    ap.add_argument("--metrics_csv", required=True)
    ap.add_argument("--out_csv", default="data/interim/smells_with_metrics.csv")
    args = ap.parse_args()

    smells = pd.read_csv(args.smells_csv, dtype=str)
    metrics = smart_read_table(Path(args.metrics_csv))

    # normalize names for join
    smells = smells.rename(columns={"project":"Project Name","package":"Package Name","class_name":"Type Name"})
    for c in ["Project Name","Package Name","Type Name"]:
        smells[c] = smells[c].astype(str).str.strip()
        metrics[c] = metrics[c].astype(str).str.strip()

    merged = pd.merge(smells, metrics, on=["Project Name","Package Name","Type Name"], how="left", suffixes=("",""))

    # restore canonical columns
    merged = merged.rename(columns={"Project Name":"project","Package Name":"package","Type Name":"class_name"})
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.out_csv, index=False)
    try:
        merged.to_parquet(args.out_csv.replace(".csv",".parquet"), index=False)
    except Exception:
        pass

    print(f"Merged rows: {len(merged)} -> {args.out_csv}")
    print(merged.head(3).to_string(index=False))

if __name__ == "__main__":
    main()
