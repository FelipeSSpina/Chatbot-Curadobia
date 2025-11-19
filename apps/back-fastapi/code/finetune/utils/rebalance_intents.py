# -*- coding: utf-8 -*-
# file: code/finetune/utils/rebalance_intents.py
# CÉLULA 1 — Reequilibra o CSV de intenções por sobre-amostragem das classes raras e/ou corte da majoritária
import argparse, pandas as pd, numpy as np, os, random
random.seed(42); np.random.seed(42)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, help="CSV com colunas text,label")
    p.add_argument("--out", required=True)
    p.add_argument("--target_min", type=int, default=60, help="mínimo por classe após oversampling")
    p.add_argument("--cap_major_label", default="nao_entendi", help="classe a capar")
    p.add_argument("--cap_major_max", type=int, default=1000, help="máximo da classe majoritária")
    args = p.parse_args()

    df = pd.read_csv(args.src)
    if not {"text","label"}.issubset(df.columns):
        raise SystemExit("CSV precisa de colunas text,label")

    parts = []
    for lab, g in df.groupby("label"):
        g = g.sample(frac=1, random_state=42)  # embaralha
        if lab == args.cap_major_label and len(g) > args.cap_major_max:
            g = g.iloc[:args.cap_major_max].copy()
        if len(g) < args.target_min:
            need = args.target_min - len(g)
            extra = g.sample(n=need, replace=True, random_state=42)
            g = pd.concat([g, extra], ignore_index=True)
        parts.append(g)

    out_df = pd.concat(parts, ignore_index=True).sample(frac=1, random_state=42)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out_df.to_csv(args.out, index=False)

    print("✔ Rebalanced:", args.out, "| dist:", out_df["label"].value_counts().to_dict())

if __name__ == "__main__":
    main()


