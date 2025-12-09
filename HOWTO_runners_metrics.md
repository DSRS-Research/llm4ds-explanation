# Runners & Metrics HOWTO

## vLLM route (GPU-friendly)
1) Launch server (example):
   python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct --port 8000 --max-model-len 8192

2) Run batch generation:
   python run_llm_vllm.py --model meta-llama/Llama-3.1-8B-Instruct --cases data/cases/cases.jsonl --prompts prompts.yaml --outdir data/generations

## llama.cpp route (CPU/Apple/low VRAM)
1) Download a compatible GGUF (e.g., llama-3.1-8b-instruct.Q4_K_M.gguf).
2) Run:
   python run_llm_llamacpp.py --model_path /path/to/model.gguf --cases data/cases/cases.jsonl --prompts prompts.yaml --outdir data/generations

## Automatic metrics
Use either generations file:
   python auto_eval.py --cases data/cases/cases.jsonl --generations data/generations/Llama-3.1-8B-Instruct.jsonl --out data/eval/auto_metrics.csv
