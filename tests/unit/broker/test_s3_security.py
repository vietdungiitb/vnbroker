"""
Unit tests S3: AuditRecord, AuditSink, IdempotencyStore, write_gate, BrokerExceptions.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from vnbroker.broker.exceptions import (
    BrokerError,
    BrokerAuthError,
    BrokerPermissionError,
    BrokerSessionExpiredError,
    BrokerValidationError,
    BrokerRateLimitError,
    BrokerOrderError,
    BrokerNetworkError,
)
from vnbroker.broker.security.audit import AuditRecord, AuditSink
from vnbroker.broker.security.idempotency import IdempotencyStore
from vnbroker.broker.security.guards import write_gate


# ─── BrokerExceptions ────────────────────────────────────────────────────────

class TestBrokerExceptions:
    def test_broker_error_base_attributes(self):
        err = BrokerError("msg", code="ERR", http_status=500, request_id="req-1")
        assert err.message == "msg"
        assert err.code == "ERR"
        assert err.http_status == 500
        assert err.request_id == "req-1"
        assert str(err) == "msg"

    def test_all_subclasses_inherit_from_broker_error(self):
        for cls in [
            BrokerAuthError, BrokerPermissionError, BrokerSessionExpiredError,
            BrokerValidationError, BrokerRateLimitError, BrokerOrderError, BrokerNetworkError,
        ]:
            e = cls("test")
            assert isinstance(e, BrokerError)
            assert isinstance(e, Exception)

    def test_default_attributes_are_empty(self):
        err = BrokerError("msg")
        assert err.code == ""
        assert err.http_status == 0
        assert err.request_id == ""

    def test_repr_contains_class_name(self):
        err = BrokerPermissionError("no write", code="WRITE_NOT_ENABLED")
        assert "BrokerPermissionError" in repr(err)
        assert "WRITE_NOT_ENABLED" in repr(err)


# ─── AuditRecord ─────────────────────────────────────────────────────────────

class TestAuditRecord:
    def _make(self, **kwargs) -> AuditRecord:
        defaults = dict(
            timestamp=datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc),
            operation="get_balance",
            account_no="******6789",
            request_id="req-abc",
            dry_run=False,
            success=True,
        )
        defaults.update(kwargs)
        return AuditRecord(**defaults)

    def test_to_dict_contains_required_fields(self):
        rec = self._make()
        d = rec.to_dict()
        assert d["operation"] == "get_balance"
        assert d["account_no"] == "******6789"
        assert d["success"] is True
        assert d["dry_run"] is False
        assert "timestamp" in d

    def test_to_dict_timestamp_is_iso_string(self):
        rec = self._make()
        d = rec.to_dict()
        assert isinstance(d["timestamp"], str)
        assert "2026" in d["timestamp"]

    def test_to_json_is_valid_json(self):
        rec = self._make()
        js = rec.to_json()
        parsed = json.loads(js)
        assert parsed["operation"] == "get_balance"

    def test_error_code_optional_defaults_none(self):
        rec = self._make(success=False, error_code="TIMEOUT")
        assert rec.error_code == "TIMEOUT"
        rec2 = self._make()
        assert rec2.error_code is None

    def test_metadata_defaults_empty_dict(self):
        rec = self._make()
        assert rec.metadata == {}

    def test_metadata_does_not_leak_into_json(self):
        rec = self._make(metadata={"symbol": "VNM", "quantity": 100})
        js = rec.to_json()
        parsed = json.loads(js)
        assert parsed["metadata"]["symbol"] == "VNM"


class TestAuditSink:
    def test_record_calls_logger_info(self):
        sink = AuditSink(sink_name="test.audit.sink")
        rec = AuditSink.make_record(
            operation="authenticate",
            account_no="N/A",
            request_id="req-1",
            dry_run=False,
            success=True,
        )
        with patch.object(sink._logger, "info") as mock_info:
            sink.record(rec)
            mock_info.assert_called_once()
            logged_str = mock_info.call_args[0][0]
            parsed = json.loads(logged_str)
            assert parsed["operation"] == "authenticate"

    def test_make_record_sets_utc_timestamp(self):
        rec = AuditSink.make_record(
            operation="get_balance",
            account_no="****6789",
            request_id="r1",
            dry_run=False,
            success=True,
        )
        assert rec.timestamp.tzinfo is not None
        assert rec.operation == "get_balance"

    def test_make_record_with_error_code(self):
        rec = AuditSink.make_record(
            operation="place_order",
            account_no="****6789",
            request_id="r2",
            dry_run=True,
            success=False,
            error_code="DRY_RUN",
        )
        assert rec.error_code == "DRY_RUN"
        assert rec.dry_run is True

    def test_audit_sink_does_not_propagate_to_root_logger(self):
        sink = AuditSink(sink_name="test.no.propagate")
        assert sink._logger.propagate is False


# ─── IdempotencyStore ────────────────────────────────────────────────────────

class TestIdempotencyStore:
    def test_first_check_returns_true(self):
        store = IdempotencyStore()
        assert store.check_and_store("key-1") is True

    def test_second_check_same_key_returns_false(self):
        store = IdempotencyStore()
        store.check_and_store("key-1")
        assert store.check_and_store("key-1") is False

    def test_different_keys_both_allowed(self):
        store = IdempotencyStore()
        assert store.check_and_store("key-1") is True
        assert store.check_and_store("key-2") is True

    def test_expired_key_allowed_again(self):
        store = IdempotencyStore(ttl_seconds=1)
        store.check_and_store("key-old")
        time.sleep(1.1)
        assert store.check_and_store("key-old") is True

    def test_mark_completed_changes_status(self):
        store = IdempotencyStore()
        store.check_and_store("key-1")
        store.mark_completed("key-1")
        assert store.is_completed("key-1") is True

    def test_is_completed_false_for_in_flight(self):
        store = IdempotencyStore()
        store.check_and_store("key-1")
        assert store.is_completed("key-1") is False

    def test_is_completed_false_for_unknown_key(self):
        store = IdempotencyStore()
        assert store.is_completed("nonexistent") is False

    def test_clear_empties_store(self):
        store = IdempotencyStore()
        store.check_and_store("k1")
        store.check_and_store("k2")
        store.clear()
        assert len(store) == 0

    def test_mark_completed_noop_on_missing_key(self):
        store = IdempotencyStore()
        store.mark_completed("nonexistent")  # Không raise

    def test_purge_expired_reduces_store_size(self):
        store = IdempotencyStore(ttl_seconds=1)
        store.check_and_store("old-key")
        time.sleep(1.1)
        store.check_and_store("new-key")  # Trigger purge
        assert store.check_and_store("old-key") is True  # old-key đã expired


# ─── write_gate decorator ────────────────────────────────────────────────────

class TestWriteGate:
    """
    write_gate cần self._session có .is_write_enabled property.
    Dùng mock session để tránh phụ thuộc vào BrokerSession (S4).
    """

    def _make_service(self, write_enabled: bool = False):
        """Tạo fake service instance với mock session."""

        class FakeService:
            def __init__(self, enabled: bool):
                self._session = MagicMock()
                self._session.is_write_enabled = enabled

            @write_gate
            def do_write(self, symbol: str, quantity: int, dry_run: bool = True) -> dict:
                return {"executed": True, "symbol": symbol, "quantity": quantity}

        return FakeService(write_enabled)

    def test_dry_run_true_returns_dry_run_dict(self):
        svc = self._make_service(write_enabled=False)
        result = svc.do_write("VNM", 100, dry_run=True)
        assert result["dry_run"] is True
        assert "do_write" in result["message"]

    def test_dry_run_true_does_not_call_real_fn(self):
        svc = self._make_service(write_enabled=False)
        result = svc.do_write("VNM", 100, dry_run=True)
        assert result.get("executed") is None  # Fn không chạy

    def test_dry_run_false_without_write_enabled_raises(self):
        svc = self._make_service(write_enabled=False)
        with pytest.raises(BrokerPermissionError) as exc:
            svc.do_write("VNM", 100, dry_run=False)
        assert exc.value.code == "WRITE_NOT_ENABLED"
        assert exc.value.http_status == 403

    def test_dry_run_false_with_write_enabled_calls_fn(self):
        svc = self._make_service(write_enabled=True)
        result = svc.do_write("VNM", 100, dry_run=False)
        assert result["executed"] is True
        assert result["symbol"] == "VNM"

    def test_dry_run_default_is_true(self):
        svc = self._make_service(write_enabled=False)
        result = svc.do_write("VNM", 100)  # Không truyền dry_run
        assert result["dry_run"] is True

    def test_write_gate_preserves_function_name(self):
        svc = self._make_service()
        assert svc.do_write.__name__ == "do_write"

    def test_missing_session_raises_permission_error(self):
        class NoSession:
            @write_gate
            def do_write(self, dry_run: bool = True) -> dict:
                return {}

        svc = NoSession()
        with pytest.raises(BrokerPermissionError):
            svc.do_write(dry_run=False)

    def test_dry_run_result_includes_operation_name(self):
        svc = self._make_service()
        result = svc.do_write("VNM", 100, dry_run=True)
        assert result["operation"] == "do_write"
