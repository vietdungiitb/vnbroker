"""
Shared fixtures cho SSI broker lane unit tests (mocked — không mạng, không creds thật).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "ssi"

SSI_ENV_VARS = (
    "VNBROKER_BROKER_SSI_CLIENT_ID",
    "VNBROKER_BROKER_SSI_API_KEY",
    "VNBROKER_BROKER_SSI_API_SECRET",
    "VNBROKER_BROKER_SSI_PRIVATE_KEY",
    "VNBROKER_BROKER_SSI_API_URL",
    "VNBROKER_BROKER_SSI_STREAM_URL",
    "VNBROKER_BROKER_SSI_DEVICE_ID",
    "VNBROKER_BROKER_SSI_TIMEOUT_SECONDS",
    "VNBROKER_BROKER_SSI_RATE_LIMIT_RPS",
    "VNBROKER_BROKER_SSI_MAX_RETRIES",
)


@pytest.fixture
def clean_ssi_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Xóa toàn bộ env SSI để test độc lập với máy chạy."""
    for var in SSI_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def ssi_env(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """Env SSI giả (giá trị TEST rõ ràng, không phải secret thật)."""
    values = {
        "VNBROKER_BROKER_SSI_CLIENT_ID": "TEST_CLIENT",
        "VNBROKER_BROKER_SSI_API_KEY": "TEST_API_KEY",
        "VNBROKER_BROKER_SSI_API_SECRET": "TEST_API_SECRET",
        "VNBROKER_BROKER_SSI_PRIVATE_KEY": "TEST_PRIVATE_KEY",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def load_fixture(name: str) -> Any:
    """Đọc fixture JSON theo tên (không phần mở rộng)."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
