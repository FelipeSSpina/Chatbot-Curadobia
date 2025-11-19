# -*- coding: utf-8 -*-
"""
Camada de alto nível para sessão/conversa.
Orquestra o SessionCache (SQLite) e expõe APIs simples para o restante do sistema.

Melhorias desta versão:
- Docstrings melhores e tipos explícitos.
- Novos utilitários: list_history(), to_dict(), list_prefs(), forget_pref(), update_slots().
- Snapshots de slots/perfil continuam sincronizados a cada append_turn().
- Mantém compatibilidade 100% com a API anterior (load/append_turn/save/...).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cache import SessionCache, DEFAULT_PATH, DEFAULT_TTL


# ------------------------------ Tipos ------------------------------------------
@dataclass
class SessionState:
    """
    Estado de uma sessão ativa (em memória).
    - slots/profile são snapshots correntes.
    - prefs contém chaves 'pref:*' persistidas (KV).
    - history/events prontos para exibir (sem o campo interno 'id').
    - meta espelha sessions.metadata_json no banco.
    """
    session_id: str
    user_id: Optional[str] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    profile: Dict[str, Any] = field(default_factory=dict)
    prefs: Dict[str, Any] = field(default_factory=dict)          # preferências persistidas (pref:*)
    history: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    fallback_events: List[Dict[str, Any]] = field(default_factory=list)  # compat retro
    meta: Dict[str, Any] = field(default_factory=dict)            # metadata_json (inclui snapshots)

    def to_dict(self) -> Dict[str, Any]:
        """Representação simples do estado — útil para debug/testes."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "slots": dict(self.slots),
            "profile": dict(self.profile),
            "prefs": dict(self.prefs),
            "history": list(self.history),
            "events": list(self.events),
            "meta": dict(self.meta),
        }


# ------------------------------ Manager ----------------------------------------
class SessionManager:
    """
    Alto nível para gerenciar sessão/conversa com persistência.
    Reune operações comuns evitando que o restante do sistema conheça detalhes do cache/DB.
    """
    def __init__(self, ttl_seconds: int = DEFAULT_TTL, db_path: Optional[str] = None):
        self.cache = SessionCache(db_path or DEFAULT_PATH, ttl_seconds=ttl_seconds)

    # -------------------- util interno --------------------
    @staticmethod
    def _strip_id(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove a chave 'id' dos dicionários (evita quebrar consumidores)."""
        out: List[Dict[str, Any]] = []
        for r in rows or []:
            if isinstance(r, dict) and "id" in r:
                d = dict(r)
                d.pop("id", None)
                out.append(d)
            else:
                out.append(r)
        return out

    # -------------------- ciclo de vida --------------------
    def load(self, session_id: str, user_id: Optional[str] = None) -> SessionState:
        """
        Carrega estado de sessão.
        Prioriza snapshots (slots_snapshot/profile_snapshot) de sessions.metadata_json.
        Cai para merge do histórico somente se os snapshots não existirem.
        """
        # Garante existência da sessão e lê metadata/snapshots
        self.cache.upsert_session(session_id, user_id=user_id)
        sess_info = self.cache.get_session(session_id) or {"metadata": {}}
        meta = dict(sess_info.get("metadata") or {})

        # 1) Slots/Profile de snapshots (rápido)
        slots_snapshot = dict(meta.get("slots_snapshot") or {})
        profile_snapshot = dict(meta.get("profile_snapshot") or {})

        # 2) Histórico e eventos (para UI/telemetria) — em ordem cronológica
        hist_raw = self.cache.history(session_id)
        events_raw = self.cache.load_events(session_id, kind=None, limit=200)
        # Não expor 'id' para os consumidores desse manager
        hist = self._strip_id(hist_raw)
        events = self._strip_id(events_raw)

        # 3) Se não houver snapshots (ex.: sessão antiga), faz merge como fallback
        if not slots_snapshot and not profile_snapshot and hist_raw:
            merged_slots: Dict[str, Any] = {}
            merged_profile: Dict[str, Any] = {}
            for t in hist_raw:
                s = t.get("slots") or {}
                p = t.get("profile") or {}
                if s:
                    merged_slots.update(s)
                if p:
                    merged_profile.update(p)
            slots_snapshot = merged_slots
            profile_snapshot = merged_profile
            # grava snapshots para as próximas cargas serem O(1)
            meta["slots_snapshot"] = slots_snapshot
            meta["profile_snapshot"] = profile_snapshot
            # também preserva dados de ambiguidade se existirem no merge
            if "clarify_count" in slots_snapshot:
                try:
                    meta["clarify_count"] = int(slots_snapshot["clarify_count"])
                except Exception:
                    pass
            if "clarify_last_ts" in slots_snapshot:
                try:
                    meta["clarify_last_ts"] = float(slots_snapshot["clarify_last_ts"])
                except Exception:
                    pass
            self.cache.update_metadata(session_id, meta)

        # 4) Prefs persistidas (KV com prefixo 'pref:')
        prefs: Dict[str, Any] = {}
        for k in self.cache.keys_by_prefix(session_id, "pref:"):
            prefs[k] = self.cache.get_kv(session_id, k)

        return SessionState(
            session_id=session_id,
            user_id=user_id,
            slots=slots_snapshot,
            profile=profile_snapshot,
            prefs=prefs,
            history=hist,
            events=events,
            meta=meta,
        )

    def append_turn(
        self,
        state: SessionState,
        role: str,
        text: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        gap_top2: Optional[float] = None,
        *,
        refresh: bool = True,  # se False, não recarrega history/events (útil para testes)
    ):
        """
        Acrescenta turno no banco e atualiza snapshots de slots/perfil em metadata_json.
        Reutiliza state.meta para evitar round-trip ao cache.
        """
        # 1) Persiste turno
        self.cache.append_turn(
            state.session_id,
            role,
            text,
            intent,
            confidence,
            gap_top2,
            state.slots,
            state.profile,
        )

        # 2) Atualiza snapshots em sessions.metadata_json (incremental) usando state.meta
        meta = dict(state.meta or {})
        meta["slots_snapshot"] = dict(state.slots or {})
        meta["profile_snapshot"] = dict(state.profile or {})
        # Campos úteis para ambiguidade/telemetria (se presentes no state.slots)
        if "clarify_count" in state.slots:
            try:
                meta["clarify_count"] = int(state.slots["clarify_count"])
            except Exception:
                pass
        if "clarify_last_ts" in state.slots:
            try:
                meta["clarify_last_ts"] = float(state.slots["clarify_last_ts"])
            except Exception:
                pass
        self.cache.update_metadata(state.session_id, meta)
        state.meta = meta  # mantém em memória para a próxima operação

        # 3) Reidrata buffers locais (opcional)
        if refresh:
            hist_raw = self.cache.history(state.session_id)
            events_raw = self.cache.load_events(state.session_id, kind=None, limit=200)
            state.history = self._strip_id(hist_raw)
            state.events = self._strip_id(events_raw)

    def save(self, state: SessionState):
        """
        No-op: persistência ocorre em append_turn / KV / events.
        Mantida por compatibilidade de interface.
        """
        pass

    # -------------------- preferências (KV) --------------------
    def remember_pref(self, session_id: str, key: str, value: Any, ttl_sec: Optional[int] = None):
        """
        Persiste preferências do usuário. Use chaves com prefixo 'pref:'.
        Ex.: remember_pref(sid, 'pref:tamanho_sup', 'M')
        """
        k = key if key.startswith("pref:") else f"pref:{key}"
        self.cache.upsert_kv(session_id, k, value, ttl_sec=ttl_sec)

    def forget_pref(self, session_id: str, key: str):
        """
        Remove uma preferência persistida. Tenta delete; se indisponível, sobrescreve com None.
        """
        k = key if key.startswith("pref:") else f"pref:{key}"
        try:
            if hasattr(self.cache, "delete_kv"):
                self.cache.delete_kv(session_id, k)  # type: ignore[attr-defined]
            else:
                self.cache.upsert_kv(session_id, k, None, ttl_sec=1)
        except Exception:
            # fallback silencioso
            self.cache.upsert_kv(session_id, k, None, ttl_sec=1)

    def list_prefs(self, session_id: str) -> Dict[str, Any]:
        """Retorna todas as chaves 'pref:*' da sessão."""
        out: Dict[str, Any] = {}
        for k in self.cache.keys_by_prefix(session_id, "pref:"):
            out[k] = self.cache.get_kv(session_id, k)
        return out

    def get_pref(self, session_id: str, key: str, default: Any = None) -> Any:
        k = key if key.startswith("pref:") else f"pref:{key}"
        return self.cache.get_kv(session_id, k, default)

    # -------------------- slots / perfil --------------------
    def set_slot(self, state: SessionState, key: str, value: Any, *, persist_snapshot: bool = False):
        """
        Atualiza slot em memória. Se persist_snapshot=True, também grava em metadata_json imediatamente,
        reutilizando state.meta (sem round-trip).
        """
        state.slots[key] = value
        if persist_snapshot:
            meta = dict(state.meta or {})
            snap = dict(meta.get("slots_snapshot") or {})
            snap[key] = value
            meta["slots_snapshot"] = snap
            # se for um dos campos de ambiguidade, mantém duplicado no nível raiz
            if key == "clarify_count":
                try:
                    meta["clarify_count"] = int(value)
                except Exception:
                    pass
            if key == "clarify_last_ts":
                try:
                    meta["clarify_last_ts"] = float(value)
                except Exception:
                    pass
            self.cache.update_metadata(state.session_id, meta)
            state.meta = meta

    def update_slots(self, state: SessionState, data: Dict[str, Any], *, persist_snapshot: bool = False):
        """
        Atualiza múltiplos slots de uma vez. Útil para pipelines.
        """
        for k, v in (data or {}).items():
            state.slots[k] = v
        if persist_snapshot:
            meta = dict(state.meta or {})
            snap = dict(meta.get("slots_snapshot") or {})
            snap.update(data or {})
            meta["slots_snapshot"] = snap
            self.cache.update_metadata(state.session_id, meta)
            state.meta = meta

    def get_slot(self, state: SessionState, key: str, default: Any = None) -> Any:
        return state.slots.get(key, default)

    def set_profile(
        self,
        state: SessionState,
        profile_dict: Dict[str, Any],
        *,
        persist: bool = True,
        persist_snapshot: bool = True
    ):
        """
        Atualiza perfil em memória; se persist=True, guarda cópia completa em KV 'profile';
        se persist_snapshot=True, atualiza profile_snapshot em metadata_json (reutiliza state.meta).
        """
        state.profile.update(profile_dict or {})
        if persist:
            self.cache.upsert_kv(state.session_id, "profile", state.profile, ttl_sec=None)
        if persist_snapshot:
            meta = dict(state.meta or {})
            meta["profile_snapshot"] = dict(state.profile or {})
            self.cache.update_metadata(state.session_id, meta)
            state.meta = meta

    def get_profile(self, state: SessionState) -> Dict[str, Any]:
        """
        Retorna perfil: tenta KV 'profile' (persistente); cai para snapshot de metadata;
        por fim, usa o perfil in-memory do state.
        """
        kv_profile = self.cache.get_kv(state.session_id, "profile", default=None)
        if kv_profile is not None:
            return kv_profile
        snap = (state.meta or {}).get("profile_snapshot")
        if isinstance(snap, dict) and snap:
            return dict(snap)
        return state.profile

    # -------------------- histórico --------------------
    def list_history(self, state: SessionState, last_n: int = 50) -> List[Dict[str, Any]]:
        """
        Retorna os últimos N turnos (sem 'id'), útil para depuração/UX.
        """
        if not state.history:
            hist_raw = self.cache.history(state.session_id)
            state.history = self._strip_id(hist_raw)
        return state.history[-max(1, last_n):]

    # -------------------- eventos --------------------
    def log_event(self, state: SessionState, kind: str, reason: str, payload: Optional[Dict[str, Any]] = None):
        self.cache.log_event(state.session_id, kind, reason, payload or {})
        events_raw = self.cache.load_events(state.session_id, kind=None, limit=200)
        state.events = self._strip_id(events_raw)

    def record_fallback_event(self, state: SessionState, kind: str, reason: str, **payload):
        """Compatibilidade retro + evento estruturado."""
        ev = {"kind": kind, "reason": reason, **payload}
        state.fallback_events.append(ev)
        # grava evento estruturado
        self.cache.log_event(state.session_id, kind, reason, payload or {})
        # também registra um turno 'meta' (útil para auditoria em histórico)
        self.cache.append_turn(
            state.session_id,
            role="meta",
            text=f"fallback:{kind}",
            intent=None,
            confidence=None,
            gap_top2=None,
            slots={"fallback_event": ev},
            profile=state.profile,
        )
        # reidrata
        hist_raw = self.cache.history(state.session_id)
        events_raw = self.cache.load_events(state.session_id, kind=None, limit=200)
        state.history = self._strip_id(hist_raw)
        state.events = self._strip_id(events_raw)

    # -------------------- manutenção & util --------------------
    def clear(self, session_id: str):
        """Limpa histórico/slots/perfil/prefs da sessão (mantém a sessão viva)."""
        self.cache.clear_session(session_id)

    def delete(self, session_id: str):
        """Apaga a sessão por completo do banco."""
        self.cache.delete_session(session_id)

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lista sessões recentes (para lista/diagnóstico em UI)."""
        return self.cache.list_recent_sessions(limit=limit)

    def export(self, session_id: str) -> Dict[str, Any]:
        """
        Export cru vindo direto do cache (inclui 'id' para diagnóstico).
        Use com cuidado — próprio para auditoria ou suporte.
        """
        return self.cache.export_session(session_id)

    def purge(self) -> tuple[int, int]:
        """Executa purga de expirados. Retorna (sessions_removidas, kv_removidas)."""
        return self.cache.purge_expired()

    def close(self) -> None:
        """Fecha a conexão SQLite persistente (útil em teardown de testes)."""
        try:
            self.cache.close()
        except Exception:
            pass
