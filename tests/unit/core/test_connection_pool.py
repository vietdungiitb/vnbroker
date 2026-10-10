"""
Tests for vnbroker.core.utils.connection_pool.

Validates singleton behavior, session reuse, thread safety, and
performance characteristics of the ConnectionPool.

Re: the shared session (plan row N2)
-------------------------------------
An earlier plan claimed the shared `requests.Session` was a race because
"cookie mutation has no lock". That was measured and REFUTED, so the shared
session was deliberately left alone. `TestSharedSessionIsThreadSafe` below
pins the refutation so a future agent does not "fix" correct concurrent code.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
import requests
from requests.adapters import HTTPAdapter

from vnbroker.core.utils.connection_pool import ConnectionPool


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset the singleton before each test."""
    ConnectionPool.reset()
    yield
    ConnectionPool.reset()


class TestSingleton:
    """Tests for singleton behavior."""

    def test_singleton(self):
        """ConnectionPool.get_instance() returns the same object."""
        pool1 = ConnectionPool.get_instance()
        pool2 = ConnectionPool.get_instance()
        assert pool1 is pool2

    def test_singleton_thread_safe(self):
        """Singleton creation is thread-safe."""
        pools = []
        lock = threading.Lock()

        def get_pool():
            pool = ConnectionPool.get_instance()
            with lock:
                pools.append(pool)

        threads = [threading.Thread(target=get_pool) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same instance
        assert all(p is pools[0] for p in pools)


class TestSessionReuse:
    """Tests for session reuse across calls."""

    def test_session_reuse(self):
        """Multiple get_session() calls return the same session object."""
        pool = ConnectionPool.get_instance()
        session1 = pool.get_session()
        session2 = pool.get_session()
        assert session1 is session2

    def test_session_is_requests_session(self):
        """get_session() returns a requests.Session instance."""
        pool = ConnectionPool.get_instance()
        session = pool.get_session()
        assert isinstance(session, requests.Session)

    def test_adapter_configuration(self):
        """Session has HTTPAdapter mounted for http:// and https://."""
        pool = ConnectionPool.get_instance()
        session = pool.get_session()

        http_adapter = session.get_adapter("http://example.com")
        https_adapter = session.get_adapter("https://example.com")

        assert isinstance(http_adapter, HTTPAdapter)
        assert isinstance(https_adapter, HTTPAdapter)

    def test_adapter_pool_size(self):
        """Adapter is configured with pool_connections=256 and pool_maxsize=256."""
        pool = ConnectionPool.get_instance()
        session = pool.get_session()

        adapter = session.get_adapter("https://example.com")
        assert adapter._pool_connections == 256
        assert adapter._pool_maxsize == 256


class TestThreadSafety:
    """Tests for thread-safe concurrent access."""

    def test_thread_safety(self):
        """Concurrent access from multiple threads returns the same session."""
        pool = ConnectionPool.get_instance()
        sessions = []
        lock = threading.Lock()

        def get_session():
            session = pool.get_session()
            with lock:
                sessions.append(session)

        threads = [threading.Thread(target=get_session) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same session object
        assert all(s is sessions[0] for s in sessions)

    def test_concurrent_session_usage(self):
        """Multiple threads can use the session concurrently without errors."""
        pool = ConnectionPool.get_instance()
        session = pool.get_session()
        errors = []
        lock = threading.Lock()

        def make_request(_):
            try:
                # Use a lightweight request to httpbin.org
                # We're testing thread safety, not the actual response
                session.get("https://httpbin.org/get", timeout=5)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(10)]
            for f in as_completed(futures):
                f.result()

        # No errors should occur from concurrent session usage
        assert len(errors) == 0


class TestSharedSessionIsThreadSafe:
    """Guard for the REFUTED claim N2 — passes before and after, on purpose.

    This is NOT evidence of a fix: the shared session was never changed.
    It exists so the measured safety of sharing one session is pinned, and so
    a future agent cannot reintroduce per-thread sessions on the strength of a
    document that was wrong.
    """

    THREADS = 8
    COOKIES_PER_THREAD = 200

    def test_cookie_jar_is_internally_locked(self):
        """requests guards its cookie jar; that lock is why sharing is safe."""
        session = ConnectionPool.get_instance().get_session()

        lock = getattr(session.cookies, "_cookies_lock", None)
        assert lock is not None, "requests no longer exposes a cookie-jar lock"
        assert hasattr(lock, "acquire") and hasattr(lock, "release")

    def test_concurrent_cookie_writes_are_not_lost(self):
        """Every concurrent cookie write must survive on the shared session."""
        session = ConnectionPool.get_instance().get_session()
        errors = []
        lock = threading.Lock()

        def writer(thread_id):
            try:
                for index in range(self.COOKIES_PER_THREAD):
                    session.cookies.set(f"c{thread_id}_{index}", "v")
            except Exception as exc:  # noqa: BLE001 - recorded and asserted below
                with lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(i,)) for i in range(self.THREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        expected = self.THREADS * self.COOKIES_PER_THREAD
        assert len(session.cookies) == expected
        assert session.cookies.get("c0_0") == "v"
        assert session.cookies.get(f"c{self.THREADS - 1}_{self.COOKIES_PER_THREAD - 1}") == "v"

    def test_one_session_is_shared_by_every_thread(self):
        """Sharing is deliberate — all threads must see the same session."""
        session = ConnectionPool.get_instance().get_session()
        seen = []
        lock = threading.Lock()

        def grab():
            got = ConnectionPool.get_instance().get_session()
            with lock:
                seen.append(got)

        threads = [threading.Thread(target=grab) for _ in range(self.THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(s is session for s in seen)


class TestPerformance:
    """Performance benchmarks (optional, can be skipped)."""

    @pytest.mark.skip(reason="Performance test - run manually with -m performance")
    def test_performance(self):
        """Benchmark shared session vs thread-local session."""
        num_requests = 100
        num_threads = 10

        # Shared session approach
        pool = ConnectionPool.get_instance()
        shared_session = pool.get_session()

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(
                    shared_session.get, "https://httpbin.org/get"
                )
                for _ in range(num_requests)
            ]
            for f in as_completed(futures):
                f.result()
        shared_time = time.time() - start

        # Thread-local approach (simulated)
        import threading
        thread_local = threading.local()

        def get_thread_session():
            session = getattr(thread_local, "session", None)
            if session is None:
                session = requests.Session()
                adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                thread_local.session = session
            return session

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(
                    get_thread_session().get, "https://httpbin.org/get"
                )
                for _ in range(num_requests)
            ]
            for f in as_completed(futures):
                f.result()
        thread_local_time = time.time() - start

        # Shared session should be faster (or at least not significantly slower)
        # We use a generous threshold to avoid flaky tests
        assert shared_time < thread_local_time * 2
