# -*- coding: utf-8 -*-

# Objetivo: ler 'tests/prompts_smoke.txt', classificar intenção e, quando for sugestão/tamanho,
# chamar o responder contextual. Imprime no console e salva CSV em code/notebooks/outputs/runs/.

import argparse, os, sys, json, time, subprocess, pathlib
import numpy as np
import pandas as pd
from joblib import load

# --------- caminhos padrão (ajustados ao seu repo) ----------
ROOT   = pathlib.Path(__file__).resolve().parents[2]
NB     = ROOT / "notebooks"
OUT    = NB / "outputs"
RUNS   = OUT / "runs"
MODELS = OUT / "models"

INTENT_DIR   = MODELS / "intents_calibrated"
CAT_INDEX    = MODELS / "catalog_index"
PROFILE_PATH = ROOT / "notebooks" / "data" / "profiles" / "cliente_exemplo.json"

RUNS.mkdir(parents=True, exist_ok=True)

# --------- util ---------
def read_prompts(path: pathlib.Path):
    lines = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s:
            lines.append(s)
    return lines

def load_intent_pack():
    meta_path = INTENT_DIR / "meta.json"
    clf_path  = INTENT_DIR / "clf.joblib"
    if not meta_path.exists() or not clf_path.exists():
        raise FileNotFoundError(f"Modelo de intenções não encontrado em: {INTENT_DIR}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # meta pode vir como {"embedder":..., "labels":[...]} OU {"meta":{...}}
    if "labels" in meta:
        labels = meta["labels"]
        embedder_name = meta.get("embedder", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        threshold = float(meta.get("threshold", 0.30))
        gap_top2  = float(meta.get("gap_top2", 0.08))
    else:
        mm = meta.get("meta", {})
        labels = mm.get("labels", [])
        embedder_name = mm.get("embedder", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        threshold = float(mm.get("threshold", 0.30))
        gap_top2  = float(mm.get("gap_top2", 0.08))
    clf = load(clf_path)
    return clf, labels, embedder_name, threshold, gap_top2

def embed_texts(embedder, texts):
    # mesma API usada no treino/infer
    return embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

def classify(clf, labels, embedder, text, threshold, gap_top2):
    vec = embed_texts(embedder, [text])
    proba = clf.predict_proba(vec)[0]  # array shape (n_classes,)
    order = np.argsort(proba)[::-1]
    i0, i1 = int(order[0]), int(order[1]) if len(order) > 1 else int(order[0])
    p0, p1 = float(proba[i0]), float(proba[i1])
    label0 = labels[i0]
    gap = p0 - p1
    # regra de confiança/gap (igual à do infer)
    if p0 < threshold or gap < gap_top2:
        return "nao_entendi", p0, gap, proba.tolist(), [(labels[i], float(proba[i])) for i in order[:3]]
    return label0, p0, gap, proba.tolist(), [(labels[i], float(proba[i])) for i in order[:3]]

def call_context_responder(query, k=5, index_dir=CAT_INDEX, profile=PROFILE_PATH):
    # usa o CLI já pronto de responder.py para garantir mesma lógica
    cmd = [
        sys.executable, str(ROOT / "code" / "context" / "responder.py"),
        "--index", str(index_dir),
        "--profile", str(profile),
        "--query", query,
        "--k", str(k)
    ]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", timeout=120)
        return out.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"[ERRO responder.py] {e.stdout}\n{e.stderr}"
    except Exception as e:
        return f"[ERRO responder.py] {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", required=True, help="arquivo de prompts (um por linha)")
    ap.add_argument("--out", default=str(RUNS / f"batch_test_{int(time.time())}.csv"))
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    prompts_path = pathlib.Path(args.prompts)
    if not prompts_path.exists():
        print(f"Arquivo de prompts não encontrado: {prompts_path}")
        sys.exit(2)

    # carrega modelo de intenções e embedder
    clf, labels, embedder_name, threshold, gap_top2 = load_intent_pack()
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer(embedder_name)

    lines = read_prompts(prompts_path)
    rows = []
    print("\n=== BATCH TEST — Curadobia ===")
    print(f"Prompts: {len(lines)} | Modelo: {embedder_name} | Labels: {labels}\n")

    for i, q in enumerate(lines, 1):
        intent, conf, gap, proba_list, top3 = classify(clf, labels, embedder, q, threshold, gap_top2)
        response = ""
        if intent in {"pedir_sugestao_produto", "tamanho_modelagem"}:
            response = call_context_responder(q, k=args.k)
        else:
            # simula resposta “templated” simples (igual chatbot faz para slots básicos)
            if intent == "saudacao":
                response = "Oi! Que bom te ver por aqui 💛 Posso te ajudar a encontrar algo?"
            elif intent == "como_comprar":
                response = "Você pode finalizar pelo site: escolha o tamanho, adicione ao carrinho e conclua o pagamento."
            elif intent == "frete_prazo":
                response = "O prazo e o valor do frete variam por CEP. Quer me passar o CEP para eu estimar?"
            elif intent == "formas_pagamento":
                response = "Aceitamos Pix e cartão (com parcelamento). Posso te orientar durante a compra!"
            elif intent == "agradecimento":
                response = "Imagina! Qualquer coisa, estou por aqui 💛"
            elif intent == "erros_plataforma":
                response = "Poxa, sinto muito! Pode me dizer qual erro apareceu? Te ajudo a resolver rapidinho."
            elif intent == "troca_devolucao_politica":
                response = "Claro! Posso te explicar direitinho os prazos e condições. Qual peça você quer trocar/devolver?"
            else:
                response = "Não entendi direitinho. Quer reformular ou me dar mais detalhes?"

        print(f"[{i:02d}] {q}")
        print(f"   -> intent={intent} | conf={conf:.3f} | gap={gap:.3f} | top3={top3}")
        print(f"   -> resposta:\n{response}\n")

        rows.append({
            "idx": i,
            "prompt": q,
            "intent": intent,
            "confidence": conf,
            "gap_top2": gap,
            "top3": json.dumps(top3, ensure_ascii=False),
            "probas": json.dumps(proba_list, ensure_ascii=False),
            "response": response
        })

    out_csv = pathlib.Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n✔ Relatório salvo em: {out_csv}")

if __name__ == "__main__":
    main()



