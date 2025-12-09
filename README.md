# Minimal pipeline step (Designite → Cases)

## 1) Parse your DesigniteJava export
```bash
python parse_designite_csv.py --input data/raw/designite/Designite_ClassSmells.csv --outdir data/interim
# or to try the bundled sample:
python parse_designite_csv.py --input designite_sample.csv --outdir data/interim
```

## 2) Build LLM-ready cases from a local clone of K-9
```bash
python build_cases_from_repo.py --repo_dir /path/to/k-9 --smells_csv data/interim/smells.csv --out data/cases/cases.jsonl --loc_limit 400
```

Outputs:
- `data/interim/smells.csv|parquet` – normalized detections
- `data/cases/cases.jsonl` – merged (code + detection) records ready for prompting

Next steps: hook `cases.jsonl` into your LLM inference script (vLLM or llama.cpp) with the `prompts.yaml` templates.

## (Optional) Merge metrics and propagate into cases
```bash
# Merge metrics into smells
python merge_smells_metrics.py --metrics_csv data/raw/metrics.csv --smells_csv data/interim/smells.csv

# Build cases using the merged file (includes metrics in each JSONL record)
python build_cases_from_repo.py --repo_dir /abs/path/to/k-9   --smells_csv data/interim/smells_with_metrics.csv   --out data/cases/cases.jsonl   --loc_limit 400
```

The runners automatically pass the metrics into the prompts; no further changes needed.
