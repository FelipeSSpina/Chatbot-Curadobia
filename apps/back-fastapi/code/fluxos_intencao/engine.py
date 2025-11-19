# -*- coding: utf-8 -*-

from dataclasses import asdict, is_dataclass

class Engine:
    def __init__(self, graph):
        self.graph = self._coerce_to_dict(graph)
        self.states    = self.graph.get("states", {}) or {}
        self.templates = self.graph.get("templates", {}) or {}
        self.fallbacks = self.graph.get("fallbacks", {}) or {}

    def _coerce_to_dict(self, graph):
        if isinstance(graph, dict):
            return graph
        if hasattr(graph, "to_dict") and callable(graph.to_dict):
            return graph.to_dict()
        if is_dataclass(graph):
            return asdict(graph)
        if hasattr(graph, "__dict__"):
            d = {}
            for k in ("states", "templates", "intents", "entities", "fallbacks"):
                if hasattr(graph, k):
                    d[k] = getattr(graph, k)
            return d or dict(graph.__dict__)
        try:
            return dict(graph)
        except Exception:
            raise TypeError(f"Tipo de grafo não suportado: {type(graph)}")

    def _eval_guard(self, guard: str, ctx: dict) -> bool:
        if not guard:
            return True
        g = guard.strip()
        neg = g.startswith("not(") or g.startswith("!has")
        key = g.replace("not(", "").replace(")", "").replace("!", "")
        key = key.replace("has(", "").replace(")", "")
        slots = ctx.get("slots", {}) if isinstance(ctx, dict) else {}
        has  = bool(ctx.get(key) or slots.get(key))
        return (not has) if neg else has

    def match_transition(self, state: str, intent: str, ctx: dict):
        trans = (self.states.get(state, {}) or {}).get("transitions", []) or []
        for t in trans:
            t_int = t.get("intent", "any")
            if t_int not in ("any", intent):
                continue
            if not self._eval_guard(t.get("guard"), ctx or {}):
                continue
            return t
        fb = (self.fallbacks or {}).get("on_unrecognized_intent")
        if fb:
            return {"intent": "any", "next": fb.get("next", state), "action": None}
        return None

    def next_state(self, state: str, intent: str, ctx: dict):
        t = self.match_transition(state, intent, ctx or {})
        if not t:
            return state, None
        return t.get("next", state), t.get("action")

    def entry_template_key(self, state: str):
        st = self.states.get(state, {}) or {}
        return (st.get("entry", {}) or {}).get("template")

    def entry_text(self, state: str) -> str:
        key = self.entry_template_key(state)
        return (self.templates or {}).get(key, "") if key else ""


