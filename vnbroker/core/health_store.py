"""Persistent health store for the AUTO source router.

The router keeps hot state in memory (monotonic clock) for ordering
decisions. This module adds a pluggable persistence layer so failure
counters and cooldowns survive process restarts:

- ``MemoryHealthStore``: volatile fallback (tests, read-only envs).
- ``SQLiteHealthStore``: file-backed default, no extra dependency.

Wall-clock timestamps are persisted (monotonic clocks are meaningless
across restarts); the router converts remaining-cooldown on load.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Dict, Tuple


StateKey = Tuple[str, str]
StateVal = Dict[str, float]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS router_health (
    module TEXT NOT NULL,
    source TEXT NOT NULL,
    failures INTEGER NOT NULL DEFAULT 0,
    cooldown_until_wall REAL NOT NULL DEFAULT 0.0,
    last_success_wall REAL,
    last_failure_wall REAL,
    PRIMARY KEY (module, source)
)
"""


class HealthStore:
    """Persistence interface for router health state (wall-clock based)."""

    def load(self) -> Dict[StateKey, StateVal]:
        """Return persisted state keyed by (module, source)."""
        raise NotImplementedError

    def save(self, state: Dict[StateKey, StateVal]) -> None:
        """Persist cooldown-remaining derived from wall-clock fields."""
        raise NotImplementedError

    def clear(self) -> None:
        """Drop all persisted state."""
        raise NotImplementedError


class MemoryHealthStore(HealthStore):
    """Volatile store — always starts empty, never persists."""

    def load(self) -> Dict[StateKey, StateVal]:
        return {}

    def save(self, state: Dict[StateKey, StateVal]) -> None:
        return None

    def clear(self) -> None:
        return None


class SQLiteHealthStore(HealthStore):
    """File-backed store using stdlib sqlite3 (WAL mode, best-effort)."""

    def __init__(self, path: str) -> None:
        self._path = os.path.expanduser(path)
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error:
            pass
        return conn

    def load(self) -> Dict[StateKey, StateVal]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT module, source, failures, cooldown_until_wall,"
                    " last_success_wall, last_failure_wall FROM router_health"
                ).fetchall()
        state: Dict[StateKey, StateVal] = {}
        for module, source, failures, cooldown_wall, succ_wall, fail_wall in rows:
            entry: StateVal = {
                "failures": float(failures or 0),
                "cooldown_until_wall": float(cooldown_wall or 0.0),
            }
            if succ_wall is not None:
                entry["last_success_wall"] = float(succ_wall)
            if fail_wall is not None:
                entry["last_failure_wall"] = float(fail_wall)
            state[(str(module), str(source))] = entry
        return state

    def save(self, state: Dict[StateKey, StateVal]) -> None:
        rows = [
            (module, source,
             int(vals.get("failures", 0)),
             float(vals.get("cooldown_until_wall", 0.0)),
             vals.get("last_success_wall"),
             vals.get("last_failure_wall"))
            for (module, source), vals in state.items()
        ]
        with self._lock:
            with self._connect() as conn:
                conn.executemany(
                    "INSERT INTO router_health"
                    " (module, source, failures, cooldown_until_wall,"
                    "  last_success_wall, last_failure_wall)"
                    " VALUES (?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(module, source) DO UPDATE SET"
                    " failures=excluded.failures,"
                    " cooldown_until_wall=excluded.cooldown_until_wall,"
                    " last_success_wall=excluded.last_success_wall,"
                    " last_failure_wall=excluded.last_failure_wall",
                    rows,
                )

    def clear(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM router_health")


def default_db_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".vnbroker", "router_health.sqlite3")


def create_store(db_path: str | None = None) -> HealthStore:
    """Create the configured store; fall back to memory on any error."""
    explicit = db_path is not None or bool(os.getenv("vnbroker_ROUTER_HEALTH_DB", "").strip())
    raw = (db_path if db_path is not None
           else os.getenv("vnbroker_ROUTER_HEALTH_DB", "")).strip()
    if not raw or raw.lower() in {"memory", ":memory:"}:
        return MemoryHealthStore()
    if not explicit and os.getenv("PYTEST_RUNNING") == "1":
        # Tests default to volatile state (no ~/.vnbroker writes);
        # persistence tests set vnbroker_ROUTER_HEALTH_DB explicitly.
        return MemoryHealthStore()
    try:
        return SQLiteHealthStore(raw if raw else default_db_path())
    except Exception:
        return MemoryHealthStore()


def wall_now() -> float:
    return time.time()
