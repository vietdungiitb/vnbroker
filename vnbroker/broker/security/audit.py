"""
vnbroker.broker.security.audit — AuditRecord + AuditSink.

RULE:
  - Logger riêng (vnbroker.broker.audit), KHÔNG dùng get_logger từ core/utils.
  - metadata dict KHÔNG được chứa api_key, otp, token, pinCode hay bất kỳ secret nào.
  - account_no phải được masked trước khi truyền vào AuditRecord
    (dùng Redactor.mask_account_no()).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

# Logger riêng — KHÔNG import get_logger từ vnbroker.core
_audit_logger = logging.getLogger("vnbroker.broker.audit")

if not _audit_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(_handler)
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False  # Không bubble lên root logger


@dataclass
class AuditRecord:
    """
    Bản ghi audit cho một operation trong broker lane.

    Security: account_no phải là masked version (***6789), metadata không chứa secret.
    """
    timestamp: datetime
    operation: str           # "authenticate" | "get_balance" | "place_order" | ...
    account_no: str          # Masked last-4 hoặc "N/A" nếu chưa authed
    request_id: str
    dry_run: bool
    success: bool
    error_code: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)  # KHÔNG chứa secret

    def to_dict(self) -> dict[str, Any]:
        """Serialize thành dict, chuyển datetime sang ISO string."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    def to_json(self) -> str:
        """Serialize thành JSON string — dùng cho log output."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class AuditSink:
    """
    Ghi AuditRecord ra structured JSON log.

    Không phụ thuộc vào logger generic của vnbroker/core/utils.
    Có thể thay thế bằng database/queue sink trong production.
    """

    def __init__(self, sink_name: str = "vnbroker.broker.audit") -> None:
        self._logger = logging.getLogger(sink_name)
        if not self._logger.handlers:
            _h = logging.StreamHandler()
            _h.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(_h)
            self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # Luôn set — không bubble lên root logger

    def record(self, rec: AuditRecord) -> None:
        """Ghi record ra log theo dạng structured JSON."""
        self._logger.info(rec.to_json())

    @staticmethod
    def make_record(
        operation: str,
        account_no: str,
        request_id: str,
        dry_run: bool,
        success: bool,
        error_code: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditRecord:
        """
        Factory helper tạo AuditRecord với timestamp UTC tự động.

        account_no nên được mask trước (Redactor.mask_account_no()).
        """
        return AuditRecord(
            timestamp=datetime.now(tz=timezone.utc),
            operation=operation,
            account_no=account_no,
            request_id=request_id,
            dry_run=dry_run,
            success=success,
            error_code=error_code,
            metadata=metadata or {},
        )
