# -*- coding: utf-8 -*-
# file: code/finetune/utils/build_intents_dataset.py
# CÉLULA 1 — Gera CSVs de treino/teste a partir do dataset_unificado, criando rótulos heurísticos quando não há 'label'
import argparse, os, re, unicodedata, pandas as pd
from sklearn.model_selection import train_test_split

CAND_TEXT = ["mensagem_clean","text","mensagem","message","utterance","frase","conteudo"]
CAND_LABEL = ["label","intent","intencao","classe","class"]

def pick_col(cols, cands, default=None):
    if default and default in cols: return default
    for c in cands:
        if c in cols: return c
    return None

def norm(s: str) -> str:
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii")
    return s.lower()

def rule_label(t: str) -> str:
    t = norm(t)
    if re.search(r"\b(oi|ola|bom dia|boa tarde|boa noite|e ai|falae)\b", t): return "saudacao"
    if re.search(r"\b(obrigad[ao]|valeu|brigad[ao])\b", t): return "agradecimento"
    if re.search(r"\b(tchau|ate logo|ate mais)\b", t): return "despedida"
    if re.search(r"\b(frete|prazo|entrega|chega quando|tempo de entrega)\b", t): return "frete_prazo"
    if re.search(r"\b(pix|boleto|cart(ao)|pagamento|parcel|juros)\b", t): return "formas_pagamento"
    if re.search(r"\b(nao consigo|erro|bug|trava|checkout|carrinho|site|app)\b", t): return "erros_plataforma"
    if re.search(r"\b(troca|devolu|estorno|arrependimento|politica)\b", t): return "troca_devolucao_politica"
    if re.search(r"\b(tem no estoque|ainda tem|disponi|tem tamanho|chega mais)\b", t): return "disponibilidade_estoque"
    if re.search(r"\b(tamanho|medid|serve|veste|modelagem|caimento)\b", t): return "tamanho_modelagem"
    if re.search(r"\b(sugest[aã]o|indica|o que combina|o que usar|me ajuda a escolher|look)\b", t): return "pedir_sugestao_produto"
    if re.search(r"\b(compr(ar|o)|como comprar|finalizar pedido|link)\b", t): return "como_comprar"
    return "nao_entendi"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--train_out", default="data/intents/curadobia_intents.csv")
    ap.add_argument("--test_out", default="data/intents/curadobia_intents_test.csv")
    ap.add_argument("--test_size", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--text_col", default=None)
    ap.add_argument("--label_col", default=None)
    ap.add_argument("--auto_rules", action="store_true")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.train_out), exist_ok=True)

    df = pd.read_csv(args.src)
    text_col = pick_col(df.columns, CAND_TEXT, default=args.text_col)
    if not text_col:
        raise SystemExit(f"Não achei coluna de texto. Disponíveis: {list(df.columns)}")

    label_col = args.label_col or pick_col(df.columns, CAND_LABEL)
    if label_col:
        df = df[[text_col, label_col]].rename(columns={text_col:"text", label_col:"label"})
    else:
        if not args.auto_rules:
            raise SystemExit("Não há coluna de label e --auto_rules não foi ligado. Rode com --auto_rules para rotular por regras.")
        df = df[[text_col]].rename(columns={text_col:"text"})
        df["label"] = df["text"].map(rule_label)

    df = df.dropna().copy()
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()

    train, test = train_test_split(df, test_size=args.test_size, random_state=args.seed, stratify=df["label"])
    train.to_csv(args.train_out, index=False)
    test.to_csv(args.test_out, index=False)

    print("✔ train:", args.train_out, len(train), train["label"].value_counts().to_dict())
    print("✔ test :", args.test_out, len(test),  test["label"].value_counts().to_dict())

if __name__ == "__main__":
    main()


