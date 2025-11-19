# -*- coding: utf-8 -*-
# file: code/context/responder.py
# Gera uma resposta contextualizada (templated) usando o índice do catálogo + perfil do cliente.
import argparse, os, json, sys, numpy as np, pandas as pd
from sentence_transformers import SentenceTransformer

# garante saída UTF-8 no Windows e flush imediato
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def load_index(index_dir):
    items_csv = os.path.join(index_dir, "items.csv")
    vecs_npy  = os.path.join(index_dir, "vectors.npy")
    meta_json = os.path.join(index_dir, "meta.json")
    if not (os.path.exists(items_csv) and os.path.exists(vecs_npy) and os.path.exists(meta_json)):
        print(f"[ERRO] Índice incompleto em {index_dir}", flush=True)
        sys.exit(1)
    items = pd.read_csv(items_csv).fillna("")
    vecs = np.load(vecs_npy)
    with open(meta_json, "r", encoding="utf-8") as f:
        meta = json.load(f)
    model = SentenceTransformer(meta["embedder"])
    return items, vecs, model

def cos_sim(a, b):
    return np.dot(a, b.T)

def parse_sizes(s):
    if not isinstance(s, str): return []
    return [x.strip().upper() for x in s.split(";") if x.strip()]

def size_match_score(profile, sizes, stock_json):
    wanted = set()
    for k in ["tamanho_superior","tamanho_inferior"]:
        v = str(profile.get(k, "")).strip().upper()
        if v: wanted.add(v)
    for v in profile.get("tamanhos_equivalentes", []):
        v = str(v).strip().upper()
        if v: wanted.add(v)
    if not wanted: 
        return 0.0
    try:
        stock = json.loads(stock_json) if isinstance(stock_json, str) else stock_json
    except Exception:
        stock = {}
    for w in wanted:
        if w in sizes:
            qty = stock.get(w, 1)
            try: qty = int(qty)
            except: qty = 1
            if qty > 0: 
                return 1.0
    if any(w in sizes for w in wanted): 
        return 0.5
    return 0.0

def style_pref_score(profile, row):
    score = 0.0
    txt = " ".join([str(row.get("brand","")), str(row.get("name","")), str(row.get("category","")),
                    str(row.get("color","")), str(row.get("material","")), str(row.get("description",""))]).lower()
    prefs = [str(p).lower() for p in profile.get("estilos_preferidos", [])]
    avoid_colors = [str(c).lower() for c in profile.get("cores_evitar", [])]
    avoid_mat = [str(m).lower() for m in profile.get("tecidos_evitar", [])]
    if prefs:
        hit = sum(1 for p in prefs if p in txt)
        score += min(0.7, 0.2*hit)
    if any(c for c in avoid_colors if c and c in str(row.get("color","")).lower()):
        score -= 0.4
    if any(m for m in avoid_mat if m and m in str(row.get("material","")).lower()):
        score -= 0.4
    return max(-0.5, min(0.7, score))

def build_prompt_style(item, profile):
    nome  = f'{item.get("brand","")} {item.get("name","")}'.strip()
    cat   = item.get("category","")
    cor   = item.get("color","")
    mat   = item.get("material","")
    preco = item.get("price","")
    sizes = parse_sizes(item.get("sizes",""))
    # tamanho sugerido simples pelo primeiro equivalente que existir na grade
    sug_tam = ""
    wanted = profile.get("tamanhos_equivalentes") or []
    if isinstance(wanted, list):
        for w in (str(x).upper() for x in wanted):
            if w in sizes: 
                sug_tam = w
                break
    elif isinstance(wanted, str) and wanted.upper() in sizes:
        sug_tam = wanted.upper()

    dicas = []
    name_lower = str(item.get("name","")).lower()
    desc_lower = str(item.get("description","")).lower()
    if "vestido" in name_lower or "vestido" in desc_lower or "vestido" in str(cat).lower():
        if "midi" in name_lower or "midi" in desc_lower:
            dicas.append("perfeito para jantar — elegante sem esforço")
        else:
            dicas.append("encaixa bem em jantares e eventos casuais chiques")
    if mat and "linho" in str(mat).lower():
        dicas.append("o linho dá caimento fresco e sofisticado")
    if not dicas:
        dicas.append("combina fácil com sandália ou mule minimalista")

    linhas = [
        f"• **{nome}** ({cat}, {cor}, {mat}) — R$ {preco}",
        f"  porquê: {'; '.join(dicas)}.",
        f"  tamanhos: {', '.join(sizes) if sizes else 'único'}" + (f" | **eu iria de {sug_tam}**" if sug_tam else "")
    ]
    return "\n".join(linhas)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    try:
        items, vecs, model = load_index(args.index)
        with open(args.profile, "r", encoding="utf-8") as f:
            profile = json.load(f)

        qvec = model.encode([args.query], normalize_embeddings=True)
        sims = cos_sim(qvec, vecs)[0]  # shape [N]

        # score composto
        rows = items.to_dict(orient="records")
        scores = []
        for i, row in enumerate(rows):
            s_sizes = size_match_score(profile, parse_sizes(row.get("sizes","")), row.get("stock_json","{}"))
            s_style = style_pref_score(profile, row)
            total = 0.7*float(sims[i]) + 0.2*s_sizes + 0.1*s_style
            scores.append((total, i, s_sizes, s_style, float(sims[i])))

        scores.sort(reverse=True)
        top = scores[:max(1, args.k)]

        if args.debug:
            print("[DEBUG] Top candidatos:", flush=True)
            for total, idx, s_sizes, s_style, s_sim in top:
                it = rows[idx]
                print(f"  -> {it.get('brand','')} {it.get('name','')} | score={total:.3f} (sim={s_sim:.3f}, size={s_sizes:.2f}, style={s_style:.2f})", flush=True)

        linhas = []
        header = f"Bora achar o look certo pra você? Olhei seu perfil e foquei nas opções que casam com seu tamanho e vibe.\n"
        for _, idx, *_ in top:
            item = rows[idx]
            linhas.append(build_prompt_style(item, profile))

        if not linhas:
            print("Não encontrei nada certeiro no seu tamanho. Quer que eu te chame no humano pra caçar alternativas?", flush=True)
            return

        resp = header + "\n".join(linhas) + "\n\nSe quiser, te ajudo a montar o look completo (bolsa + sapato) e já separo no seu tamanho."
        print(resp, flush=True)
    except Exception as e:
        import traceback
        print("[ERRO] Falha ao gerar resposta:", e, flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    main()


