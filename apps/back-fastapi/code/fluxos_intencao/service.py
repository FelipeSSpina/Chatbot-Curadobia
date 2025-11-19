# -*- coding: utf-8 -*-

from .config import Config
from .yaml_loader import load_yaml
from .engine import Engine
import re

_CATS = {"vestido","blusa","calca","saia","macaquinho","casaco","acessorio","outro"}
_TAMS = {"pp","p","m","g","gg","xg","xxg","36","38","40","42","44","46"}
_RE_CEP    = re.compile(r"\b(\d{5})-?(\d{3})\b")
_RE_PEDIDO = re.compile(r"\b([A-Z0-9]{5,10})\b", re.I)

def _extract_entities(texto: str):
    ents = {}
    if not isinstance(texto, str):
        return ents
    t = texto.strip()
    m = _RE_CEP.search(t)
    if m:
        ents["geo.cep"] = f"{m.group(1)}-{m.group(2)}"
    if "pedido" in t.lower():
        m2 = _RE_PEDIDO.search(t)
        if m2:
            ents["pedido.id"] = m2.group(1).upper()
    m3 = re.search(r"\btam(?:anho)?[: ]?([pxmg]{1,2}|\d{2})\b", t, flags=re.I)
    if m3:
        ents["tamanho_ref"] = m3.group(1).lower()
    else:
        for tm in _TAMS:
            if re.search(rf"\b{re.escape(tm)}\b", t, flags=re.I):
                ents["tamanho_ref"] = tm
                break
    for c in _CATS:
        if re.search(rf"\b{re.escape(c)}\b", t, flags=re.I):
            ents["categoria"] = c
            break
    return ents

def _render_template_str(tpl: str, ctx: dict) -> str:
    if not tpl:
        return ""
    text = str(tpl)
    slots = (ctx or {}).get("slots", {}) if isinstance(ctx, dict) else {}
    flat = dict(ctx or {})
    flat.update(slots)
    for k, v in flat.items():
        text = text.replace("{{"+str(k)+"}}", str(v))
    return text

class _RuleBasedNLU:
    def predict(self, text: str):
        s = (text or "").lower()
        def has_any(words): return any(w in s for w in words)
        if has_any(["oi","olá","ola","bom dia","boa tarde","boa noite"]): intent="saudacao"
        elif has_any(["tamanho","serve","medida","manequim","numeracao","numeração"]): intent="tamanho_modelagem"
        elif has_any(["frete","prazo","entrega","cep"]): intent="frete_prazo"
        elif has_any(["preço","preco","pix","cartão","cartao","boleto","pagar","pagamento"]): intent="formas_pagamento"
        elif has_any(["estoque","disponível","disponivel","tem no tamanho","tem tamanho","tem cor"]): intent="disponibilidade"
        elif has_any(["onde comprar","link","comprar","quero comprar"]): intent="onde_comprar"
        elif has_any(["humano","atendente","pessoa"]): intent="falar_com_humano"
        elif has_any(["tchau","obrigado","valeu"]): intent="despedida"
        else: intent="outros"
        return {"intent": intent, "conf": 1.0, "probs": {}, "top1": intent, "top2": intent, "gap": 1.0}

class ChatService:
    def __init__(self):
        self.cfg    = Config.from_env()
        raw         = load_yaml(self.cfg.fluxos_yaml)
        self.engine = Engine(raw)
        self.state  = "START"
        self.ctx    = {"slots": {}}
        try:
            from .nlu import IntentClassifier
            self.nlu = IntentClassifier(
                models_dir=self.cfg.models_dir,
                embedder_name=self.cfg.hf_embedder,
                intent_threshold=self.cfg.intent_threshold,
                top2_gap=self.cfg.intent_top2_gap,
                fallback_label=self.cfg.fallback_label or "outros",
            )
        except Exception:
            self.nlu = _RuleBasedNLU()

    def _run_action(self, action_name: str):
        if not action_name:
            return {}
        try:
            from . import actions as _actions
            fn = getattr(_actions, action_name, None)
            if callable(fn):
                return fn(dict(self.ctx)) or {}
        except Exception:
            return {}
        return {}

    def handle(self, user_text: str, ctx: dict | None = None):
        if isinstance(ctx, dict):
            self.ctx.update({k:v for k,v in ctx.items() if k != "slots"})
            if "slots" in ctx and isinstance(ctx["slots"], dict):
                self.ctx["slots"].update(ctx["slots"])
        ents = _extract_entities(user_text or "")
        self.ctx.update(ents)
        self.ctx.setdefault("slots", {}).update(ents)

        pred   = self.nlu.predict(user_text)
        intent = pred.get("intent") or "outros"

        ns, act = self.engine.next_state(self.state, intent, self.ctx)
        if ns == "CAPTURA_INTENCAO":
            ns, act = self.engine.next_state(ns, intent, self.ctx)

        if act:
            out = self._run_action(act)
            if isinstance(out, dict):
                self.ctx.update(out)
                self.ctx.setdefault("slots", {}).update(out)

        tpl_key = self.engine.entry_template_key(ns)
        if tpl_key:
            tpl_text = (self.engine.templates or {}).get(tpl_key, "")
            reply = _render_template_str(tpl_text, self.ctx) or "..."
        else:
            reply = self.engine.entry_text(ns) or "..."

        self.state = ns
        meta  = {"estado": self.state, "intencao": intent, "acao": act}
        return reply, meta


