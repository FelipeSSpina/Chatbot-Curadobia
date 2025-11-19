# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
from typing import Dict, Any

# Aqui ficam “efeitos colaterais” (BD, integrações, etc.). Por enquanto, stubs simples.

# === Catálogo normalizado: paths padrão (NB05 outputs) ===
_CAT_DF = None
_BASE   = Path(__file__).resolve().parents[1] / "notebooks" / "notebook05_outputs"
_PARQ   = _BASE / "catalogo_normalizado.parquet"
_CSV    = _BASE / "catalogo_normalizado.csv"
def gerar_sugestoes(ctx: Dict[str,Any]) -> Dict[str,Any]:
    return {"sugestoes": ["vestido midi", "blusa cetim", "saia evasê"]}

def consultar_estoque(ctx: Dict[str,Any]) -> Dict[str,Any]:
    q = ctx.get("produto.nome") or ctx.get("categoria") or "produto"
    return {"lista": [f"{q} A (P/M)", f"{q} B (M/G)"]}

def cotar_frete(ctx: Dict[str,Any]) -> Dict[str,Any]:
    cep = ctx.get("geo.cep", "00000-000")
    return {"prazo": "3–5 dias úteis", "cep": cep}

def consultar_status_pedido(ctx: Dict[str,Any]) -> Dict[str,Any]:
    pid = ctx.get("pedido.id", "—")
    return {"status": "em separação", "pedido": pid}

def consultar_politica_troca(ctx: Dict[str,Any]) -> Dict[str,Any]:
    return {"texto": "Trocas em até 7 dias, peça sem uso e etiqueta."}

def estimar_tamanho(ctx: Dict[str,Any]) -> Dict[str,Any]:
    return {"tamanho": ctx.get("tamanho_ref", "M"), "caimento": "regular"}

def sugerir_looks(ctx: Dict[str,Any]) -> Dict[str,Any]:
    peca = ctx.get("categoria", "peça básica")
    ocas = ctx.get("ocasiao", "casual")
    return {"peca": peca, "ocasiao": ocas}

def responder_kb_materiais(ctx: Dict[str,Any]) -> Dict[str,Any]:
    return {"resposta": "Viscose com elastano; lavar a frio, secar à sombra."}

def abrir_chamado(ctx: Dict[str,Any]) -> Dict[str,Any]:
    return {"ticket": "CHM-12345"}


def _load_catalog() -> pd.DataFrame:
    """Carrega catálogo normalizado de parquet ou CSV (fallback)."""
    global _CAT_DF
    if _CAT_DF is not None:
        return _CAT_DF
    if _PARQ.exists():
        _CAT_DF = pd.read_parquet(_PARQ)
    elif _CSV.exists():
        _CAT_DF = pd.read_csv(_CSV)
    else:
        # fallback mínimo para não quebrar
        _CAT_DF = pd.DataFrame([
            {"sku":"VEST001","nome":"Vestido midi alfaiataria","categoria":"vestido","preco":590.0,"cor":"preto","tamanhos":"P,M,G","tecido":"alfaiataria","elasticidade":"baixa","estoque":12,"descricao":"Vestido midi de alfaiataria para trabalho e eventos"},
            {"sku":"BLUS002","nome":"Blusa cetim gola laço","categoria":"blusa","preco":329.0,"cor":"off","tamanhos":"P,M,G,GG","tecido":"cetim","elasticidade":"media","estoque":7,"descricao":"Blusa de cetim leve, ótima para trabalho e jantar"},
        ])
    return _CAT_DF


# === Redação com LLM afinado (TinyLlama/Mistral + LoRA) ===
from typing import Dict, Any
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from pathlib import Path

_LLM_BASE_TXT = Path(__file__).resolve().parents[1] / "notebooks" / "modelos" / "llm_consultora" / "base_model_name.txt"
_ADAPTER_DIR  = Path(__file__).resolve().parents[1] / "notebooks" / "modelos" / "llm_consultora" / "adapter"
_TOK_DIR      = Path(__file__).resolve().parents[1] / "notebooks" / "modelos" / "llm_consultora"

_LLM_OBJ = {}
def _load_llm():
    if _LLM_OBJ.get("model"):
        return _LLM_OBJ["model"], _LLM_OBJ["tok"], _LLM_OBJ["device"]
    if not _LLM_BASE_TXT.exists() or not _ADAPTER_DIR.exists():
        return None, None, "cpu"
    base_name = _LLM_BASE_TXT.read_text(encoding="utf-8").strip()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(_TOK_DIR, use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(base_name, torch_dtype=torch.float32)
    base = base.to(device)
    model = PeftModel.from_pretrained(base, _ADAPTER_DIR)
    model.eval()
    _LLM_OBJ.update({"model": model, "tok": tok, "device": device})
    return model, tok, device

def redigir_resposta_consultora(ctx: Dict[str,Any]) -> Dict[str,Any]:
    """
    Recebe contexto (ex.: lista_sugestoes, consulta, medidas) e devolve 'resposta_llm'.
    Usa adapter treinado; se ausente, devolve um texto padrão elegante.
    """
    model, tok, device = _load_llm()
    user_msg = ctx.get("mensagem") or ctx.get("consulta") or "Quero sugestões com base no meu perfil."
    extra = []
    if ctx.get("lista_sugestoes"):
        extra.append("Sugestões iniciais: " + str(ctx["lista_sugestoes"]))
    if ctx.get("tamanho_ref"):
        extra.append(f"Tamanho de referência: {ctx['tamanho_ref']}")
    if ctx.get("ocasiao"):
        extra.append(f"Ocasiao: {ctx['ocasiao']}")
    if ctx.get("budget"):
        extra.append(f"Budget aproximado: R$ {ctx['budget']}")
    if ctx.get("cor"):
        extra.append(f"Preferência de cor: {ctx['cor']}")
    hint = "\n".join(extra)

    if model is None or tok is None:
        base = "Perfeito! Para o seu perfil, separei opções que equilibram conforto e elegância."
        if ctx.get("lista_sugestoes"):
            base += " " + str(ctx["lista_sugestoes"])
        base += " Quer que eu te mande os links e compare tamanhos para garantir o caimento? ✨"
        return {"resposta_llm": base}

    system = "Você é a BIBI, consultora de moda da Curadobia. Tom acolhedor, direto e elegante. Responda em pt-BR."
    prompt = f"<s>[SYSTEM]\n{system}\n[/SYSTEM]\n[USER]\n{user_msg}\n{hint}\n[/USER]\n[ASSISTANT]\n"
    inputs = tok(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=160, do_sample=True, top_p=0.9, temperature=0.7, eos_token_id=tok.eos_token_id)
    gen = tok.decode(out[0], skip_special_tokens=False)
    resp = gen.split("[ASSISTANT]\n")[-1].split("</s>")[0].strip()
    return {"resposta_llm": resp}


