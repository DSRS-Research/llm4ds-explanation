#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch runner for Ollama local inference (http://localhost:11434).

Use with models like `llama3`, `mistral`, `codellama`, etc.

Example:
  python scripts/run_llm_ollama.py --model llama3 \
    --cases data/cases/cases.jsonl \
    --prompts configs/prompts.yaml \
    --outdir data/generations
"""
import argparse, json, time, requests, yaml, hashlib
from pathlib import Path

def sha1(x: str) -> str:
    return hashlib.sha1(x.encode()).hexdigest()[:10]

def read_cases(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def generate_ollama(model: str, prompt: str, system: str,
                    temperature: float, top_p: float, max_tokens: int):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": f"{system}\n\n{prompt}",
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        },
        "stream": False,
    }
    t0 = time.time()
    resp = requests.post(url, json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    text = data.get("response", "")
    dur = time.time() - t0
    return text, round(dur, 2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="data/cases/cases.jsonl")
    ap.add_argument("--prompts", default="configs/prompts.yaml")
    ap.add_argument("--model", default="llama3")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--top_p", type=float, default=0.9)
    ap.add_argument("--max_tokens", type=int, default=768)
    ap.add_argument("--outdir", default="data/generations")
    args = ap.parse_args()

    prompts = yaml.safe_load(open(args.prompts, "r", encoding="utf-8"))
    system = prompts["system"]
    cases_path = Path(args.cases)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"{args.model}_ollama.jsonl"

    with open(out_path, "a", encoding="utf-8") as fout:
        for case in read_cases(cases_path):
            metrics = case.get("metrics", {}) or {}
            vars = {
                "smell_type": case["smell_type"],
                "detector_reason": case["detector_reason"],
                "code_excerpt": case["code_excerpt"],
                "problem_bullets": case["detector_reason"],
                "NOF": metrics.get("NOF", ""),
                "NOPF": metrics.get("NOPF", ""),
                "NOM": metrics.get("NOM", ""),
                "NOPM": metrics.get("NOPM", ""),
                "LOC": metrics.get("LOC", ""),
                "WMC": metrics.get("WMC", ""),
                "DIT": metrics.get("DIT", ""),
                "LCOM": metrics.get("LCOM", ""),
                "FANIN": metrics.get("FANIN", ""),
                "FANOUT": metrics.get("FANOUT", ""),
            }
            ph = sha1(json.dumps(vars, sort_keys=True))
            record = {
                "case_id": case["case_id"],
                "file_path": case["file_path"],
                "model": args.model,
                "prompt_hash": ph,
            }
            for key in ["explain_template","refactor_template","meta_validation_template"]:
                prompt = prompts[key].format(**vars)
                text, dur = generate_ollama(args.model, prompt, system,
                                            args.temperature, args.top_p, args.max_tokens)
                record[key.replace("_template","")] = {
                    "text": text,
                    "latency_s": dur,
                }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote generations to {out_path}")

if __name__ == "__main__":
    main()
