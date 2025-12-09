#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch runner using llama.cpp python bindings.
Requires: pip install llama-cpp-python
Provide --model_path to the GGUF file on disk.
"""
import argparse, json, time, hashlib
from pathlib import Path
import yaml
from llama_cpp import Llama

def sha1(x): return hashlib.sha1(x.encode()).hexdigest()[:10]

def read_cases(p: Path):
    with p.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="data/cases/cases.jsonl")
    ap.add_argument("--prompts", default="prompts.yaml")
    ap.add_argument("--model_path", required=True, help="Path to GGUF model")
    ap.add_argument("--n_gpu_layers", type=int, default=0)
    ap.add_argument("--n_ctx", type=int, default=8192)
    ap.add_argument("--max_tokens", type=int, default=768)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--top_p", type=float, default=0.9)
    ap.add_argument("--outdir", default="data/generations")
    args = ap.parse_args()

    prompts = yaml.safe_load(open(args.prompts, "r", encoding="utf-8"))
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / (Path(args.model_path).stem + ".jsonl")

    llm = Llama(model_path=args.model_path, n_ctx=args.n_ctx, n_gpu_layers=args.n_gpu_layers, verbose=False)

    def chat(prompt):
        t0=time.time()
        out = llm.create_chat_completion(
            messages=[
                {"role":"system","content":prompts["system"]},
                {"role":"user","content":prompt},
            ],
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            seed=42
        )
        t = time.time() - t0
        text = out["choices"][0]["message"]["content"]
        tokens_in = out.get("usage",{}).get("prompt_tokens")
        tokens_out = out.get("usage",{}).get("completion_tokens")
        return text, t, tokens_in, tokens_out

    with open(out_path, "a", encoding="utf-8") as fout:
        for case in read_cases(Path(args.cases)):
            vars = {
              "smell_type": case["smell_type"],
              "detector_reason": case["detector_reason"],
              "code_excerpt": case["code_excerpt"],
              "problem_bullets": case["detector_reason"],
              "NOF": (case.get("metrics", {}) or {}).get("NOF", ""),
              "NOPF": (case.get("metrics", {}) or {}).get("NOPF", ""),
              "NOM": (case.get("metrics", {}) or {}).get("NOM", ""),
              "NOPM": (case.get("metrics", {}) or {}).get("NOPM", ""),
              "LOC": (case.get("metrics", {}) or {}).get("LOC", ""),
              "WMC": (case.get("metrics", {}) or {}).get("WMC", ""),
              "DIT": (case.get("metrics", {}) or {}).get("DIT", ""),
              "LCOM": (case.get("metrics", {}) or {}).get("LCOM", ""),
              "FANIN": (case.get("metrics", {}) or {}).get("FANIN", ""),
              "FANOUT": (case.get("metrics", {}) or {}).get("FANOUT", "")
            }
            ph = sha1(json.dumps(vars, sort_keys=True))
            rec = {
              "case_id": case["case_id"],
              "model": str(Path(args.model_path).name),
              "prompt_hash": ph,
              "config": {"max_tokens": args.max_tokens, "temperature": args.temperature, "top_p": args.top_p}
            }
            for key in ["explain_template","refactor_template","meta_validation_template"]:
                text, dur, tin, tout = chat(prompts[key].format(**vars))
                rec[key.replace("_template","")] = {
                    "text": text,
                    "latency_s": round(dur,2),
                    "tokens_in": tin,
                    "tokens_out": tout
                }
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote generations to {out_path}")

if __name__ == "__main__":
    main()
