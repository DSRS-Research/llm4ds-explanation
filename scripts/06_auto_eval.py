#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute simple automatic metrics:
 - detector_alignment (keyword overlap & soft cues)
 - principle_grounding (mentions + justification)
 - refactoring_coverage (taxonomy hits) & specificity (identifier-anchored steps)
 - hallucination_flags (identifiers not present in snippet)
 - readability (presence of numbered/bulleted steps)

Inputs:
  - data/cases/cases.jsonl
  - data/generations/<model>.jsonl
Outputs:
  - data/eval/auto_metrics.csv
"""
import argparse, json, re
from pathlib import Path
import pandas as pd

REFAC_TAXONOMY = {
    "Extract Class": [r"extract class", r"split class", r"move cluster of methods"],
    "Extract Method": [r"extract method", r"split method", r"decompose"],
    "Move Method": [r"move method", r"relocate method", r"move.*to (a )?class"],
    "Move Field": [r"move field", r"relocate field"],
    "Introduce Parameter Object": [r"parameter object", r"introduce parameter object"],
    "Replace Conditional with Polymorphism": [r"replace conditional with polymorphism", r"strategy pattern"],
    "Introduce Interface": [r"introduce interface", r"create interface"],
    "Encapsulate Field": [r"encapsulate field", r"make field private", r"getter|setter"],
    "Reduce Parameter List": [r"reduce parameter list", r"introduce builder"],
    "Facade": [r"facade"],
    "Strategy": [r"strategy pattern"],
    "Observer": [r"observer pattern"],
}

SMELL_CUES = {
    "deficient encapsulation": ["public field", "exposes field", "mutable state", "information hiding"],
    "unnecessary abstraction": ["no methods", "few members", "redundant abstraction", "wrapper"],
    "unutilized abstraction": ["unused", "dead code", "not referenced"],
    "god class": ["many methods", "too many responsibilities", "high coupling", "low cohesion", "WMC", "CBO", "LCOM"],
    "feature envy": ["uses foreign data", "move method", "low cohesion", "high coupling to"],
    "long method": ["too long", "many branches", "extract method", "cyclomatic"],
}

PRINCIPLES = ["single responsibility", "open-closed", "dependency inversion", "liskov", "interface segregation",
              "law of demeter", "cohesion", "coupling", "encapsulation", "polymorphism"]

IDENT_PAT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

def keyword_score(smell_type: str, reason: str, explanation: str) -> float:
    cues = set()
    st = smell_type.lower()
    for k,v in SMELL_CUES.items():
        if k in st:
            cues.update(v)
    # add words from reason
    for w in re.findall(r"[A-Za-z]{4,}", reason.lower()):
        if w in {"this","because","that","class","following","fields","methods","smell","detected"}:
            continue
        cues.add(w)
    if not cues:
        return 0.0
    hits = sum(1 for c in cues if c in explanation.lower())
    return round(hits / len(cues), 3)

def principle_grounding(text: str) -> float:
    mentions = [p for p in PRINCIPLES if p in text.lower()]
    # crude justification: presence of because/due to + a principle
    just = 1 if re.search(r"(because|due to|therefore).*(cohesion|coupling|encapsulation|responsibilit)", text.lower()) else 0
    return min(1.0, (len(mentions) > 0) * 0.5 + just * 0.5)

def tag_refactorings(text: str):
    hits = set()
    for label, pats in REFAC_TAXONOMY.items():
        if any(re.search(p, text.lower()) for p in pats):
            hits.add(label)
    return hits

def identifiers_in(text: str):
    return set([m.group(0) for m in IDENT_PAT.finditer(text)])

def identifier_hallucinations(snippet: str, commentary: str):
    ids_snip = identifiers_in(snippet)
    ids_comm = identifiers_in(commentary)
    # filter out common english words (tiny stoplist)
    stop = {"the","and","for","with","this","that","from","class","method","field","public","private","protected","return","new","null","true","false"}
    ids_comm = {i for i in ids_comm if i.lower() not in stop}
    extra = ids_comm - ids_snip
    return sorted(list(extra))

def readability_score(text: str) -> int:
    bullets = len(re.findall(r"^(\s*[-*]|\s*\d+\.)", text, re.M))
    if bullets >= 6: return 3
    if bullets >= 3: return 2
    if bullets >= 1: return 1
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="data/cases/cases.jsonl")
    ap.add_argument("--generations", required=True, help="Path to generations jsonl")
    ap.add_argument("--out", default="data/eval/auto_metrics.csv")
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    cases = {}
    with open(args.cases, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                j = json.loads(line)
                cases[j["case_id"]] = j

    rows = []
    with open(args.generations, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            g = json.loads(line)
            c = cases.get(g["case_id"])
            if not c: 
                continue
            exp = g["explain"]["text"]
            ref = g["refactor"]["text"]
            combined = exp + "\n" + ref
            align = keyword_score(c["smell_type"], c["detector_reason"], exp)
            grounding = principle_grounding(exp)
            ref_hits = tag_refactorings(ref)
            coverage = len(ref_hits)
            # specificity: count of identifiers mentioned that exist in snippet
            ids_snip = identifiers_in(c["code_excerpt"])
            ids_ref = identifiers_in(ref)
            specificity = len(ids_ref & ids_snip)
            halluc = identifier_hallucinations(c["code_excerpt"], combined)
            read = readability_score(ref)
            rows.append({
                "case_id": g["case_id"],
                "model": g["model"],
                "smell_type": c["smell_type"],
                "detector_alignment": align,
                "principle_grounding": grounding,
                "refactoring_coverage": coverage,
                "specificity_ids": specificity,
                "hallucinations_count": len(halluc),
                "readability": read
            })
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"Wrote {len(rows)} rows to {args.out}")

if __name__ == "__main__":
    main()
