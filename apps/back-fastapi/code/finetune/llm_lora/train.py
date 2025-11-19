# -*- coding: utf-8 -*-
# file: code/finetune/llm_lora/train.py
"""
Treina adapter LoRA para voz/estilo BIA.
JSONL esperado: {"instruction": "...", "input": "...", "output": "..."}
"""
import argparse, os, random, torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, DataCollatorForLanguageModeling, Trainer
from peft import LoraConfig, get_peft_model, TaskType

def set_seed(s): random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)

def fmt(ex):
    instr = ex.get("instruction",""); ctx = ex.get("input",""); out = ex.get("output","")
    prompt = f"[SYSTEM] Você é a BIA, consultora de moda da Curadobia.\n[CONTEXT]\n{ctx}\n[USER]\n{instr}\n[ASSISTANT]\n"
    return {"text": prompt + out}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base_model", default="mistral-7b-instruct")
    p.add_argument("--data", required=True)
    p.add_argument("--save_dir", required=True)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch_size", type=int, default=2)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--lora_dropout", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()

    set_seed(a.seed)
    os.makedirs(a.save_dir, exist_ok=True)

    ds = load_dataset("json", data_files=a.data, split="train").map(fmt, remove_columns=["instruction","input","output"])
    tok = AutoTokenizer.from_pretrained(a.base_model, use_fast=True); tok.pad_token = tok.eos_token
    def tok_fn(b): return tok(b["text"], truncation=True, max_length=2048)
    ds_tok = ds.map(tok_fn, batched=True, remove_columns=["text"])

    model = AutoModelForCausalLM.from_pretrained(a.base_model, torch_dtype=torch.bfloat16, device_map="auto")
    lcfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=a.lora_r, lora_alpha=a.lora_alpha, lora_dropout=a.lora_dropout,
                      target_modules=["k_proj","q_proj","v_proj","o_proj"])
    model = get_peft_model(model, lcfg)

    collator = DataCollatorForLanguageModeling(tok, mlm=False)
    args = TrainingArguments(output_dir=a.save_dir, num_train_epochs=a.epochs, per_device_train_batch_size=a.batch_size,
                             learning_rate=a.lr, logging_steps=20, save_strategy="epoch",
                             bf16=True, gradient_checkpointing=True, report_to="none")
    Trainer(model=model, args=args, train_dataset=ds_tok, data_collator=collator).train()
    model.save_pretrained(a.save_dir); tok.save_pretrained(a.save_dir)


