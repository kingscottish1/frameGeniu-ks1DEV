"""AES-256-GCM encrypted SQLite. Ciphertext at rest, 0600 runtime file."""

from __future__ import annotations

import atexit
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from app.security.crypto import get_vault
from app.utils.env import env
from app.utils.file_manager import ROOT
from app.utils.logger import get_logger


def data_folder() -> Path:
    raw = env("FRAMEGENIUS_DATA_DIR")
    return Path(raw) if raw else ROOT / "data"

log = get_logger("db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at REAL NOT NULL,
    last_login REAL,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until REAL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    csrf TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    ip TEXT,
    user_agent TEXT
);
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_used REAL,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    stage TEXT,
    message TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    params_json TEXT,
    result_json TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS secrets (
    key TEXT PRIMARY KEY,
    value_enc TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    user TEXT,
    action TEXT NOT NULL,
    detail TEXT,
    ip TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_hash ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts);
"""


class EncryptedDB:
    def __init__(self, folder: Path | None = None) -> None:
        self.folder = Path(folder) if folder else data_folder()
        self.folder.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.folder, 0o700)
        except OSError:
            pass
        self.enc_path = self.folder / "framegenius.db.enc"
        self.runtime_path = self.folder / ".runtime.db"
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._dirty = False
        self.recovered = False
        self._open()
        atexit.register(self.close)

    def _wipe_runtime(self) -> None:
        for leftover in (
            self.runtime_path,
            Path(str(self.runtime_path) + "-wal"),
            Path(str(self.runtime_path) + "-shm"),
        ):
            leftover.unlink(missing_ok=True)

    def _quarantine_vault(self, reason: str) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        broken = self.enc_path.with_name(f"framegenius.db.enc.broken-{stamp}")
        try:
            if self.enc_path.exists():
                self.enc_path.replace(broken)
                log.warning("Unreadable vault moved to {} ({})", broken.name, reason)
        except OSError:
            self.enc_path.unlink(missing_ok=True)
            log.warning("Unreadable vault deleted ({})", reason)
        self._wipe_runtime()
        self.recovered = True

    def _open(self) -> None:
        vault = get_vault()
        if self.enc_path.exists() and self.enc_path.stat().st_size > 40:
            try:
                plain = vault.decrypt_db(self.enc_path.read_bytes())
                self.runtime_path.write_bytes(plain)
            except Exception as exc:
                # Typical after a second install: .env got a new key, old .enc remains.
                # Quarantine the old file and start a fresh vault so INSTALL never dies.
                self._quarantine_vault(str(exc))
        self._chmod_runtime()
        conn = sqlite3.connect(str(self.runtime_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA secure_delete = ON")
        conn.executescript(SCHEMA)
        conn.commit()
        self._conn = conn
        self.flush()

    def _chmod_runtime(self) -> None:
        try:
            os.chmod(self.runtime_path, 0o600)
        except OSError:
            pass

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database is closed")
        return self._conn

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, tuple(params))
            self._dirty = True
            return cur

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.conn.execute(sql, tuple(params)))

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def commit(self) -> None:
        with self._lock:
            self.conn.commit()
            self._dirty = True

    def flush(self) -> None:
        """Write AES-GCM snapshot to disk."""
        with self._lock:
            if self._conn is None:
                return
            self.conn.commit()
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            raw = Path(self.runtime_path).read_bytes()
            blob = get_vault().encrypt_db(raw)
            tmp = self.enc_path.with_suffix(".enc.tmp")
            tmp.write_bytes(blob)
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            tmp.replace(self.enc_path)
            self._dirty = False

    def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            try:
                self.flush()
            except Exception as exc:
                log.warning("DB flush on close failed: {}", exc)
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def put_secret(self, key: str, value: str) -> None:
        token = get_vault().encrypt_text(value)
        self.execute(
            "INSERT INTO secrets(key, value_enc, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_enc=excluded.value_enc, updated_at=excluded.updated_at",
            (key, token, time.time()),
        )
        self.commit()
        self.flush()

    def get_secret(self, key: str) -> str | None:
        row = self.one("SELECT value_enc FROM secrets WHERE key=?", (key,))
        if not row:
            return None
        try:
            return get_vault().decrypt_text(row["value_enc"])
        except Exception:
            return None

    def audit(self, action: str, *, user: str | None = None, detail: str = "", ip: str = "") -> None:
        self.execute(
            "INSERT INTO audit(ts, user, action, detail, ip) VALUES(?,?,?,?,?)",
            (time.time(), user, action, detail[:2000], ip),
        )
        self.commit()

    def upsert_task(self, record: dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO tasks(task_id, state, progress, stage, message, created_at, updated_at, params_json, result_json, error)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(task_id) DO UPDATE SET
                state=excluded.state,
                progress=excluded.progress,
                stage=excluded.stage,
                message=excluded.message,
                updated_at=excluded.updated_at,
                params_json=excluded.params_json,
                result_json=excluded.result_json,
                error=excluded.error
            """,
            (
                record.get("task_id"),
                str(record.get("state")),
                int(record.get("progress") or 0),
                record.get("stage"),
                record.get("message"),
                float(record.get("created_at") or time.time()),
                float(record.get("updated_at") or time.time()),
                json.dumps(record.get("params") or {}, ensure_ascii=False),
                json.dumps(record.get("result") or {}, ensure_ascii=False),
                record.get("error"),
            ),
        )
        self.commit()

    def load_tasks(self) -> list[dict[str, Any]]:
        out = []
        for row in self.query("SELECT * FROM tasks ORDER BY created_at DESC"):
            out.append(
                {
                    "task_id": row["task_id"],
                    "state": row["state"],
                    "progress": row["progress"],
                    "stage": row["stage"],
                    "message": row["message"] or "",
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "params": json.loads(row["params_json"] or "{}"),
                    "result": json.loads(row["result_json"] or "{}"),
                    "error": row["error"],
                    "logs": [],
                }
            )
        return out

    def delete_task(self, task_id: str) -> None:
        self.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
        self.commit()


_DB: EncryptedDB | None = None
_DB_LOCK = threading.Lock()


def get_db() -> EncryptedDB:
    global _DB
    with _DB_LOCK:
        if _DB is None:
            _DB = EncryptedDB()
        return _DB
