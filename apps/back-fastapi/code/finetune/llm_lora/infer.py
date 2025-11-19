# -*- coding: utf-8 -*-
# file: code/finetune/llm_lora/infer.py
"""
Gera respostas aplicando adapter LoRA.
Entrada JSONL: {"instruction": "...", "input": "..."}
Saída JSONL: {"instruction","input","output"}
"""
import argparse, os, json, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from tqdm import tqdm

def build_prompt(instr, ctx):
    return f"[SYSTEM] Você é a BIA, consultora de moda da Curadobia.\n[CONTEXT]\n{ctx}\n[USER]\n{instr}\n[ASSISTANT]\n"

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base_model", default="mistral-7b-instruct")
    p.add_argument("--adapter", required=True)
    p.add_argument("--prompts", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max_new_tokens", type=int, default=256)
    a = p.parse_args()

    tok = AutoTokenizer.from_pretrained(a.base_model, use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(a.base_model, torch_dtype=torch.bfloat16, device_map="auto")
    model = PeftModel.from_pretrained(base, a.adapter)

    outs = []
    with open(a.prompts, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Inferindo"):
            ex = json.loads(line)
            prompt = build_prompt(ex.get("instruction",""), ex.get("input",""))
            inp = tok(prompt, return_tensors="pt").to(model.device)
            gen = model.generate(**inp, max_new_tokens=a.max_new_tokens, do_sample=True, top_p=0.9, temperature=0.7)
            text = tok.decode(gen[0], skip_special_tokens=True)
            resp = text.split("[ASSISTANT]")[-1].strip()
            outs.append({"instruction": ex.get("instruction",""), "input": ex.get("input",""), "output": resp})

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fo:
        for o in outs: fo.write(json.dumps(o, ensure_ascii=False) + "\n")


