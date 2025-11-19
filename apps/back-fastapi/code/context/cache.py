# -*- coding: utf-8 -*-
"""
Cache de sessões/turnos persistente em SQLite com TTL, KV-store e eventos.

Cria notebooks/outputs/cache/sessions.db com quatro tabelas:
- sessions(id, user_id, ttl_seconds, created_at, updated_at, metadata_json)
- turns(id, session_id, ts, role, text, intent, confidence, gap_top2, slots_json, profile_json)
- kv(id, session_id, key, value_json, updated_at, expires_at)
- events(id, session_id, ts, kind, reason, payload_json)

Principais recursos (otimizados):
- Conexão persistente com RLock e PRAGMAs (WAL/NORMAL)
- history() e load_events() em ordem cronológica (ORDER BY id ASC)
- LIMIT com placeholders (sem f-strings) para consistência
- get_kv com expiração e deleção na **mesma transação**
- export_session() busca KV de preferências em **uma consulta**
- purge_expired() usa **DELETE direto** para KV e sessões (com ON DELETE CASCADE)
- upsert_session / touch_session / list_recent_sessions
- append_turn / history
- upsert_kv / get_kv / delete_kv / keys_by_prefix
- log_event / load_events
- clear_session / delete_session / export_session
- close() e contexto (__enter__/__exit__) para testes/teardown
"""

from __future__ import annotations
import sqlite3, json, time, os, threading
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_PATH = os.environ.get("BIA_CACHE_DB", "notebooks/outputs/cache/sessions.db")
DEFAULT_TTL = int(os.environ.get("BIA_CACHE_TTL", "3600"))  # 1h padrão

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  ttl_seconds INTEGER NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  ts REAL NOT NULL,
  role TEXT NOT NULL,
  text TEXT,
  intent TEXT,
  confidence REAL,
  gap_top2 REAL,
  slots_json TEXT,
  profile_json TEXT,
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS kv (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  key   TEXT NOT NULL,
  value_json TEXT,
  updated_at REAL NOT NULL,
  expires_at REAL,
  UNIQUE(session_id, key),
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  ts REAL NOT NULL,
  kind   TEXT NOT NULL,
  reason TEXT,
  payload_json TEXT,
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_turns_session_id ON turns(session_id, id);
CREATE INDEX IF NOT EXISTS ix_kv_session_key ON kv(session_id, key);
CREATE INDEX IF NOT EXISTS ix_kv_expires ON kv(expires_at);
CREATE INDEX IF NOT EXISTS ix_events_session_id ON events(session_id, id);
"""

def _json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return json.dumps(str(obj), ensure_ascii=False)

def _json_loads(s: Optional[str]) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return s  # devolve string crua se não for JSON


class SessionCache:
    """Cache com conexão persistente e operações otimizadas para sessões longas."""

    def __init__(self, db_path: str = DEFAULT_PATH, ttl_seconds: int = DEFAULT_TTL):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.RLock()
        # conexão persistente
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout=3000;")
        # schema + pragmas
        self._conn.executescript(SCHEMA)

    # -------------------- contexto & lifecycle --------------------
    def __enter__(self) -> "SessionCache":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def _now(self) -> float:
        return time.time()

    # -------------------- sessões --------------------
    def upsert_session(self, session_id: str, user_id: Optional[str] = None, **metadata):
        now = self._now()
        meta = _json_dumps(metadata or {})
        with self._lock:
            cur = self._conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,))
            if cur.fetchone():
                self._conn.execute(
                    "UPDATE sessions SET user_id=?, ttl_seconds=?, updated_at=?, metadata_json=? WHERE id=?",
                    (user_id, self.ttl_seconds, now, meta, session_id),
                )
            else:
                self._conn.execute(
                    "INSERT INTO sessions(id, user_id, ttl_seconds, created_at, updated_at, metadata_json) VALUES(?,?,?,?,?,?)",
                    (session_id, user_id, self.ttl_seconds, now, now, meta),
                )

    def touch_session(self, session_id: str, user_id: Optional[str] = None):
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET updated_at=?, user_id=COALESCE(?, user_id) WHERE id=?",
                (self._now(), user_id, session_id),
            )

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "ttl_seconds": row["ttl_seconds"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": _json_loads(row["metadata_json"]) or {},
        }

    def update_metadata(self, session_id: str, metadata: Dict[str, Any]) -> None:
        """Atualiza metadata_json preservando a sessão."""
        now = self._now()
        meta = _json_dumps(metadata or {})
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET metadata_json=?, updated_at=? WHERE id=?",
                (meta, now, session_id),
            )

    def list_recent_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "updated_at": r["updated_at"],
                    "created_at": r["created_at"],
                    "ttl_seconds": r["ttl_seconds"],
                }
            )
        return out

    # -------------------- turnos --------------------
    def append_turn(
        self,
        session_id: str,
        role: str,
        text: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        gap_top2: Optional[float] = None,
        slots: Optional[Dict[str, Any]] = None,
        profile: Optional[Dict[str, Any]] = None,
    ):
        self.upsert_session(session_id)  # garante sessão
        now = self._now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO turns(session_id, ts, role, text, intent, confidence, gap_top2, slots_json, profile_json) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    now,
                    role,
                    text,
                    intent,
                    confidence,
                    gap_top2,
                    _json_dumps(slots or {}),
                    _json_dumps(profile or {}),
                ),
            )
            self._conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))

    def history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna histórico em ordem cronológica (ORDER BY id ASC)."""
        params: List[Any] = [session_id]
        base = (
            "SELECT id, ts, role, text, intent, confidence, gap_top2, slots_json, profile_json "
            "FROM turns WHERE session_id=? ORDER BY id ASC"
        )
        if limit and int(limit) > 0:
            base += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(base, tuple(params)).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "role": r["role"],
                    "text": r["text"],
                    "intent": r["intent"],
                    "confidence": r["confidence"],
                    "gap_top2": r["gap_top2"],
                    "slots": _json_loads(r["slots_json"]) or {},
                    "profile": _json_loads(r["profile_json"]) or {},
                }
            )
        return out

    def seen_products(self, session_id: str) -> List[str]:
        hist = self.history(session_id, limit=200)
        seen: List[str] = []
        for t in hist:
            ids = (t.get("slots") or {}).get("products_shown") or []
            for pid in ids:
                if pid not in seen:
                    seen.append(pid)
        return seen

    # -------------------- KV com TTL --------------------
    def upsert_kv(self, session_id: str, key: str, value: Any, *, ttl_sec: Optional[int] = None) -> None:
        """Armazena 'key' para a sessão. ttl_sec=None → sem expiração."""
        self.upsert_session(session_id)
        now = self._now()
        exp = None if ttl_sec is None else now + max(0, int(ttl_sec))
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO kv(session_id, key, value_json, updated_at, expires_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(session_id, key)
                DO UPDATE SET value_json=excluded.value_json,
                              updated_at=excluded.updated_at,
                              expires_at=excluded.expires_at
                """,
                (session_id, key, _json_dumps(value), now, exp),
            )
            self._conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))

    def get_kv(self, session_id: str, key: str, default: Any = None) -> Any:
        now = self._now()
        with self._lock:
            row = self._conn.execute(
                "SELECT value_json, expires_at FROM kv WHERE session_id=? AND key=?",
                (session_id, key),
            ).fetchone()
            if not row:
                return default
            exp = row["expires_at"]
            if exp is not None and float(exp) < now:
                # expirada: remover na MESMA transação
                self._conn.execute("DELETE FROM kv WHERE session_id=? AND key=?", (session_id, key))
                return default
            return _json_loads(row["value_json"])

    def delete_kv(self, session_id: str, key: Optional[str] = None, prefix: Optional[str] = None) -> int:
        if not key and not prefix:
            return 0
        with self._lock:
            if key:
                cur = self._conn.execute("DELETE FROM kv WHERE session_id=? AND key=?", (session_id, key))
                return cur.rowcount or 0
            else:
                cur = self._conn.execute(
                    "DELETE FROM kv WHERE session_id=? AND key LIKE ?",
                    (session_id, f"{prefix}%"),
                )
                return cur.rowcount or 0

    def keys_by_prefix(self, session_id: str, prefix: str) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key FROM kv WHERE session_id=? AND key LIKE ? ORDER BY key",
                (session_id, f"{prefix}%"),
            ).fetchall()
        return [r["key"] for r in rows]

    # -------------------- eventos --------------------
    def log_event(self, session_id: str, kind: str, reason: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self.upsert_session(session_id)
        now = self._now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(session_id, ts, kind, reason, payload_json) VALUES(?,?,?,?,?)",
                (session_id, now, kind, reason, _json_dumps(payload or {})),
            )
            self._conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))

    def load_events(self, session_id: str, kind: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        base = "SELECT id, ts, kind, reason, payload_json FROM events WHERE session_id=?"
        params: List[Any] = [session_id]
        if kind:
            base += " AND kind=?"
            params.append(kind)
        base += " ORDER BY id ASC"
        if limit and int(limit) > 0:
            base += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(base, tuple(params)).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "ts": r["ts"],
                "kind": r["kind"],
                "reason": r["reason"],
                "payload": _json_loads(r["payload_json"]) or {}
            })
        return out

    # -------------------- manutenção --------------------
    def purge_expired(self) -> Tuple[int, int]:
        """
        Remove KV expirados e sessões cujo (updated_at + ttl_seconds) < agora.
        Retorna (sessions_removidas, kv_removidas).
        """
        now = self._now()
        with self._lock:
            cur_kv = self._conn.execute("DELETE FROM kv WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
            removed_kv = cur_kv.rowcount or 0
            # Deleta sessões expiradas (ttl_seconds > 0). ON DELETE CASCADE limpa turns/kv/events.
            cur_sess = self._conn.execute(
                "DELETE FROM sessions WHERE ttl_seconds > 0 AND (updated_at + ttl_seconds) < ?",
                (now,),
            )
            removed_sessions = cur_sess.rowcount or 0
        return int(removed_sessions), int(removed_kv)

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM turns  WHERE session_id=?", (session_id,))
            self._conn.execute("DELETE FROM kv     WHERE session_id=?", (session_id,))
            self._conn.execute("DELETE FROM events WHERE session_id=?", (session_id,))
            self._conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (self._now(), session_id))

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            # excluir sessão (CASCADE remove filhos)
            self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    # -------------------- export/diagnóstico --------------------
    def export_session(self, session_id: str) -> Dict[str, Any]:
        """Exporta sessão com turns (ASC), eventos (ASC) e **prefs** via fetch único."""
        sess = self.get_session(session_id) or {"id": session_id}
        turns = self.history(session_id, limit=1000)
        # fetch único das preferências (prefixo "pref:")
        with self._lock:
            kv_rows = self._conn.execute(
                "SELECT key, value_json FROM kv WHERE session_id=? AND key LIKE 'pref:%' ORDER BY key",
                (session_id,),
            ).fetchall()
        prefs = {r["key"]: _json_loads(r["value_json"]) for r in kv_rows}
        events = self.load_events(session_id, kind=None, limit=1000)
        return {"session": sess, "turns": turns, "prefs": prefs, "events": events}

