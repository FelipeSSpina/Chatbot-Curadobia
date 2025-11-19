import sqlite3, json, time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  name TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  started_at REAL,
  state TEXT,
  context_json TEXT
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  ts REAL,
  role TEXT,       -- 'user' | 'bot'
  text TEXT,
  intent TEXT,
  meta_json TEXT
);
"""

class DB:
    def __init__(self, path: Path):
        self.path = str(path)
        self._ensure()

    def _ensure(self):
        with sqlite3.connect(self.path) as con:
            con.executescript(DDL)

    def insert_session(self, sid: str, user_id: str):
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT OR REPLACE INTO sessions(id,user_id,started_at,state,context_json) VALUES(?,?,?,?,?)",
                        (sid, user_id, time.time(), "START", "{}"))

    def get_session(self, sid: str) -> Optional[Tuple[str,str,float,str,Dict]]:
        with sqlite3.connect(self.path) as con:
            cur = con.execute("SELECT id,user_id,started_at,state,context_json FROM sessions WHERE id=?", (sid,))
            row = cur.fetchone()
            if not row: return None
            return row[0], row[1], row[2], row[3], json.loads(row[4] or "{}")

    def update_session(self, sid: str, state: str, context: Dict[str,Any]):
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE sessions SET state=?, context_json=? WHERE id=?",
                        (state, json.dumps(context, ensure_ascii=False), sid))

    def insert_message(self, sid: str, role: str, text: str, intent: Optional[str]=None, meta: Dict[str,Any]=None):
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO messages(session_id,ts,role,text,intent,meta_json) VALUES(?,?,?,?,?,?)",
                        (sid, time.time(), role, text, intent, json.dumps(meta or {}, ensure_ascii=False)))

    def history(self, sid: str, limit: int=30) -> List[Dict[str,Any]]:
        with sqlite3.connect(self.path) as con:
            cur = con.execute(
                "SELECT ts,role,text,intent,meta_json FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (sid, limit))
            return [{"ts":r[0],"role":r[1],"text":r[2],"intent":r[3],"meta":json.loads(r[4] or "{}")} for r in cur.fetchall()]

