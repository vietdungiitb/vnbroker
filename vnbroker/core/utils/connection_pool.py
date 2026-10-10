"""
Shared connection pool for vnbroker API clients.

Provides a singleton ConnectionPool that maintains a single requests.Session
with a large connection pool, eliminating per-thread TLS handshakes in bulk
operations.
"""

import threading
from typing import Optional

import requests
from requests.adapters import HTTPAdapter


class ConnectionPool:
    """
    Singleton connection pool for shared HTTP sessions.

    Creates one requests.Session with HTTPAdapter configured for high
    concurrency (pool_connections=256, pool_maxsize=256). The session is
    thread-safe for connection pooling, so all threads can share it safely.
    """

    _instance: Optional["ConnectionPool"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the connection pool with a shared session."""
        self._session: requests.Session = self._create_session()

    @staticmethod
    def _create_session() -> requests.Session:
        """Create a requests.Session with a large connection pool."""
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=256, pool_maxsize=256)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    @classmethod
    def get_instance(cls) -> "ConnectionPool":
        """
        Get the singleton ConnectionPool instance.

        Thread-safe lazy initialization using double-checked locking.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_session(self) -> requests.Session:
        """
        Get the shared requests.Session.

        The session is thread-safe for connection pooling, so it can be
        used concurrently from multiple threads.
        """
        return self._session

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance (primarily for testing).

        Creates a fresh ConnectionPool on next get_instance() call.
        """
        with cls._lock:
            cls._instance = None
