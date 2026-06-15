"""
vnbroker.broker.security.idempotency — IdempotencyStore với TTL in-memory.

Dùng trước khi gửi write request để ngăn duplicate order/transfer.
In-memory alpha implementation — có thể swap sang Redis-backed store sau.

RULE: request_id do caller generate (UUID4); store chỉ detect duplicate.
"""
from __future__ import annotations

import time


class IdempotencyStore:
    """
    In-memory idempotency key store với TTL.

    Không dùng Redis (dependency quá nặng cho alpha).
    Thread-safety: single-thread assumption trong alpha.
    """

    # Marker phân biệt in-flight vs completed
    _COMPLETED_MARKER = "__COMPLETED__"

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._store: dict[str, tuple[float, str]] = {}  # key → (timestamp, status)
        self._ttl = ttl_seconds

    def check_and_store(self, key: str) -> bool:
        """
        Kiểm tra và đăng ký idempotency key.

        Returns:
            True  — key chưa tồn tại (hoặc đã expired) → được phép tiến hành.
            False — key đã tồn tại và còn trong TTL → duplicate, từ chối.

        Side-effect: Nếu True, đăng ký key với status IN_FLIGHT + dọn expired keys.
        """
        self._purge_expired()

        if key in self._store:
            return False  # Duplicate trong TTL window

        self._store[key] = (time.monotonic(), "IN_FLIGHT")
        return True

    def mark_completed(self, key: str) -> None:
        """
        Đánh dấu key đã hoàn thành (IN_FLIGHT → COMPLETED).
        Không làm gì nếu key không tồn tại.
        """
        if key in self._store:
            ts, _ = self._store[key]
            self._store[key] = (ts, self._COMPLETED_MARKER)

    def is_completed(self, key: str) -> bool:
        """Trả về True nếu key đã mark_completed và còn trong TTL."""
        if key not in self._store:
            return False
        ts, status = self._store[key]
        if time.monotonic() - ts > self._ttl:
            return False
        return status == self._COMPLETED_MARKER

    def clear(self) -> None:
        """Xoá toàn bộ store — dùng cho testing hoặc reset sau logout."""
        self._store.clear()

    def _purge_expired(self) -> None:
        """Dọn dẹp các entry đã quá TTL."""
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]

    def __len__(self) -> int:
        """Số entry hiện tại (bao gồm cả in-flight và completed)."""
        return len(self._store)
