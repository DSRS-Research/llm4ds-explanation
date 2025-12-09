PY=python

all: cases run-vllm eval

smells:
	$(PY) scripts/01_parse_designite_csv.py --input data/raw/designite_sample.csv --outdir data/interim

merge:
	$(PY) scripts/02_merge_smells_metrics.py --metrics_csv data/raw/metrics_sample.csv --smells_csv data/interim/smells.csv

cases: smells merge
	$(PY) scripts/03_build_cases_from_repo.py --repo_dir /abs/path/to/k-9 --smells_csv data/interim/smells_with_metrics.csv --out data/cases/cases.jsonl --loc_limit 400

run-vllm:
	$(PY) scripts/05_run_llm_vllm.py --model meta-llama/Llama-3.1-8B-Instruct --cases data/cases/cases.jsonl --prompts configs/prompts.yaml --outdir data/generations

run-llamacpp:
	$(PY) scripts/05_run_llm_llamacpp.py --model_path /path/to/model.gguf --cases data/cases/cases.jsonl --prompts configs/prompts.yaml --outdir data/generations

eval:
	$(PY) scripts/06_auto_eval.py --cases data/cases/cases.jsonl --generations data/generations/Llama-3.1-8B-Instruct.jsonl --out data/eval/auto_metrics.csv
