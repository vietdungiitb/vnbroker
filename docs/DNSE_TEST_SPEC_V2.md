# DNSE Explorer — Test Specification v2
**Phiên bản:** 2.0 (mở rộng từ DNSE_TEST_PLAN.md)  
**Ngày duyệt:** 2026-05-07  
**Áp dụng cho:** Scope A (explorer/dnse) + Scope B (trade.py refactor)

---

## 1. Cấu trúc file test cần tạo

```
tests/
├── unit/
│   └── explorer/
│       └── dnse/
│           ├── __init__.py             ← tạo mới (rỗng)
│           ├── test_quote.py           ← unit tests DNSEQuote
│           ├── test_listing.py         ← unit tests DNSEListing
│           ├── test_helpers.py         ← unit tests _parse_ohlc, _parse_trades, v.v.
│           └── fixtures.py             ← dữ liệu mẫu dùng chung
└── integration/
    └── test_dnse_explorer.py           ← integration test, skip nếu thiếu env
```

---

## 2. File `tests/unit/explorer/dnse/fixtures.py`

```python
"""Fixture dữ liệu mẫu cho DNSE Explorer unit tests."""

# OHLC response giả lập — format bars list; live DNSE smoke cũng có thể trả top-level dict t/o/h/l/c/v
SAMPLE_OHLC_BARS = [
    {"t": 1704067200, "o": 67000.0, "h": 68500.0, "l": 66800.0, "c": 68000.0, "v": 1234567},
    {"t": 1704153600, "o": 68000.0, "h": 69000.0, "l": 67500.0, "c": 68500.0, "v": 987654},
    {"t": 1704240000, "o": 68500.0, "h": 70000.0, "l": 68000.0, "c": 69500.0, "v": 1100000},
]

# Response body với key "bars" (kiểu DNSE trả về)
SAMPLE_OHLC_BODY_BARS = {"bars": SAMPLE_OHLC_BARS}

# Response body với key "data" (fallback)
SAMPLE_OHLC_BODY_DATA = {"data": SAMPLE_OHLC_BARS}

# Response body là list trực tiếp
SAMPLE_OHLC_BODY_LIST = SAMPLE_OHLC_BARS

# Trades response
SAMPLE_TRADES = [
    {"t": 1704067200, "p": 68000.0, "v": 500, "s": "B"},
    {"t": 1704067260, "p": 67900.0, "v": 300, "s": "S"},
    {"t": 1704067320, "p": 68100.0, "v": 1000, "s": "B"},
]

SAMPLE_TRADES_BODY = {"trades": SAMPLE_TRADES}

# Security definition response; live DNSE smoke trả list[dict] và price_depth normalize bằng pd.json_normalize
SAMPLE_SECDEF = {
    "symbol": "VNM",
    "name": "CTCP Sữa Việt Nam",
    "boardId": "HOSE",
    "lotSize": 100,
    "type": "STOCK",
}

# Instruments response
SAMPLE_INSTRUMENTS = [
    {"symbol": "VNM", "marketId": "HOSE", "name": "CTCP Sữa Việt Nam", "type": "STOCK"},
    {"symbol": "HPG", "marketId": "HOSE", "name": "CTCP Tập đoàn Hoa Phát", "type": "STOCK"},
    {"symbol": "ACB", "marketId": "HNX",  "name": "NHTM Cổ phần Á Châu", "type": "STOCK"},
]

SAMPLE_INSTRUMENTS_BODY = {"instruments": SAMPLE_INSTRUMENTS}
```

---

## 3. File `tests/unit/explorer/dnse/test_helpers.py`

Test các helper functions độc lập với class.

### 3.1 Tests cho `_normalize_interval`

```python
import pytest
from vnbroker.explorer.dnse.quote import _normalize_interval

class TestNormalizeInterval:
    def test_daily_alias(self):
        assert _normalize_interval("daily") == "1D"
        assert _normalize_interval("DAILY") == "1D"
        assert _normalize_interval("day")   == "1D"
        assert _normalize_interval("d")     == "1D"

    def test_standard_passthrough(self):
        assert _normalize_interval("1D") == "1D"
        assert _normalize_interval("1W") == "1W"
        assert _normalize_interval("1M") == "1M"
        assert _normalize_interval("1H") == "1H"

    def test_intraday(self):
        assert _normalize_interval("1m")  == "1m"
        assert _normalize_interval("5m")  == "5m"
        assert _normalize_interval("15m") == "15m"
        assert _normalize_interval("30m") == "30m"

    def test_unknown_passthrough(self):
        assert _normalize_interval("4H") == "4H"
```

### 3.2 Tests cho `_to_unix_seconds`

```python
from vnbroker.explorer.dnse.quote import _to_unix_seconds

class TestToUnixSeconds:
    def test_known_date(self):
        ts = _to_unix_seconds("2024-01-01")
        assert ts == 1704067200   # 2024-01-01 00:00:00 UTC

    def test_another_date(self):
        ts = _to_unix_seconds("2024-06-15")
        assert ts == 1718409600

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            _to_unix_seconds("15/06/2024")
```

### 3.3 Tests cho `_extract_ohlc_list`

```python
from vnbroker.explorer.dnse.quote import _extract_ohlc_list
from tests.unit.explorer.dnse.fixtures import (
    SAMPLE_OHLC_BARS, SAMPLE_OHLC_BODY_BARS,
    SAMPLE_OHLC_BODY_DATA, SAMPLE_OHLC_BODY_LIST,
)

class TestExtractOhlcList:
    def test_none_returns_empty(self):
        assert _extract_ohlc_list(None) == []

    def test_list_passthrough(self):
        result = _extract_ohlc_list(SAMPLE_OHLC_BODY_LIST)
        assert result == SAMPLE_OHLC_BARS

    def test_dict_bars_key(self):
        result = _extract_ohlc_list(SAMPLE_OHLC_BODY_BARS)
        assert result == SAMPLE_OHLC_BARS

    def test_dict_data_key_fallback(self):
        result = _extract_ohlc_list(SAMPLE_OHLC_BODY_DATA)
        assert result == SAMPLE_OHLC_BARS

    def test_dict_no_known_key(self):
        result = _extract_ohlc_list({"unknown": "value"})
        assert result == []
```

### 3.4 Tests cho `_parse_ohlc`

```python
import pandas as pd
from vnbroker.explorer.dnse.quote import _parse_ohlc
from tests.unit.explorer.dnse.fixtures import SAMPLE_OHLC_BARS

class TestParseOhlc:
    def test_empty_returns_empty_df(self):
        df = _parse_ohlc([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert list(df.columns) == ["time","open","high","low","close","volume"]

    def test_columns_present(self):
        df = _parse_ohlc(SAMPLE_OHLC_BARS)
        for col in ("time","open","high","low","close","volume"):
            assert col in df.columns, f"Thiếu cột: {col}"

    def test_dtypes(self):
        df = _parse_ohlc(SAMPLE_OHLC_BARS)
        assert df["time"].dtype == "datetime64[ns]", "time phải là datetime64[ns]"
        assert df["open"].dtype  == "float64"
        assert df["high"].dtype  == "float64"
        assert df["low"].dtype   == "float64"
        assert df["close"].dtype == "float64"
        assert str(df["volume"].dtype) == "Int64"

    def test_sorted_ascending(self):
        import copy
        # Đảo ngược thứ tự records
        reversed_records = list(reversed(SAMPLE_OHLC_BARS))
        df = _parse_ohlc(reversed_records)
        times = df["time"].tolist()
        assert times == sorted(times), "Phải sắp xếp tăng dần theo time"

    def test_no_timezone(self):
        df = _parse_ohlc(SAMPLE_OHLC_BARS)
        assert df["time"].dt.tz is None, "time không được có timezone"

    def test_row_count(self):
        df = _parse_ohlc(SAMPLE_OHLC_BARS)
        assert len(df) == len(SAMPLE_OHLC_BARS)

    def test_values_correct(self):
        df = _parse_ohlc(SAMPLE_OHLC_BARS)
        assert df.iloc[0]["open"]  == 67000.0
        assert df.iloc[0]["close"] == 68000.0
        assert df.iloc[0]["volume"] == 1234567
```

### 3.5 Tests cho `_parse_trades`

```python
from vnbroker.explorer.dnse.quote import _parse_trades
from tests.unit.explorer.dnse.fixtures import SAMPLE_TRADES

class TestParseTrades:
    def test_empty_returns_empty_df(self):
        df = _parse_trades([])
        assert df.empty
        assert list(df.columns) == ["time","price","volume","side"]

    def test_columns(self):
        df = _parse_trades(SAMPLE_TRADES)
        for col in ("time","price","volume","side"):
            assert col in df.columns

    def test_price_dtype(self):
        df = _parse_trades(SAMPLE_TRADES)
        assert df["price"].dtype == "float64"

    def test_volume_dtype(self):
        df = _parse_trades(SAMPLE_TRADES)
        assert str(df["volume"].dtype) == "Int64"
```

---

## 4. File `tests/unit/explorer/dnse/test_quote.py`

### 4.1 Setup mocks

```python
import os
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from tests.unit.explorer.dnse.fixtures import (
    SAMPLE_OHLC_BODY_BARS, SAMPLE_OHLC_BARS,
    SAMPLE_TRADES_BODY, SAMPLE_TRADES,
    SAMPLE_SECDEF,
)


def make_dnse_quote(symbol="VNM"):
    """Helper tạo DNSEQuote với mock DNSEClient, không cần API key thật."""
    with patch.dict(os.environ, {"DNSE_API_KEY": "fake_key", "DNSE_API_SECRET": "fake_secret"}):
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client   = MagicMock()
            MockClient.return_value = mock_client
            
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote(symbol=symbol)
            return q, mock_client
```

### 4.2 Test `__init__`

```python
class TestDNSEQuoteInit:
    def test_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("DNSE_API_KEY", raising=False)
        monkeypatch.delenv("DNSE_API_SECRET", raising=False)
        from vnbroker.explorer.dnse.quote import DNSEQuote
        with pytest.raises(ValueError, match="DNSE cần api_key"):
            DNSEQuote("VNM")

    def test_raises_without_secret(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "key")
        monkeypatch.delenv("DNSE_API_SECRET", raising=False)
        from vnbroker.explorer.dnse.quote import DNSEQuote
        with pytest.raises(ValueError):
            DNSEQuote("VNM")

    def test_symbol_uppercased(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "k")
        monkeypatch.setenv("DNSE_API_SECRET", "s")
        with patch("vnbroker.connector.dnse.client.DNSEClient"):
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote("vnm")
            assert q.symbol == "VNM"

    def test_env_credentials_used(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "env_key")
        monkeypatch.setenv("DNSE_API_SECRET", "env_secret")
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            from vnbroker.explorer.dnse.quote import DNSEQuote
            DNSEQuote("VNM")
            MockClient.assert_called_once_with(
                api_key="env_key", api_secret="env_secret", show_log=False
            )
```

### 4.3 Test `history()`

```python
class TestDNSEQuoteHistory:
    def setup_method(self):
        self.patch_env = patch.dict(
            os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}
        )
        self.patch_env.start()

    def teardown_method(self):
        self.patch_env.stop()

    def _make_quote(self, get_ohlc_return):
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_ohlc.return_value = (200, get_ohlc_return)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote("VNM")
            return q

    def test_returns_dataframe(self):
        q = self._make_quote(SAMPLE_OHLC_BODY_BARS)
        df = q.history(start="2024-01-01", end="2024-01-03")
        assert isinstance(df, pd.DataFrame)

    def test_correct_columns(self):
        q = self._make_quote(SAMPLE_OHLC_BODY_BARS)
        df = q.history(start="2024-01-01", end="2024-01-03")
        for col in ("time","open","high","low","close","volume"):
            assert col in df.columns

    def test_row_count(self):
        q = self._make_quote(SAMPLE_OHLC_BODY_BARS)
        df = q.history(start="2024-01-01", end="2024-01-03")
        assert len(df) == len(SAMPLE_OHLC_BARS)

    def test_empty_on_api_error(self):
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_ohlc.side_effect = Exception("timeout")
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote("VNM")
            df = q.history(start="2024-01-01")
            assert df.empty

    def test_interval_daily_sends_D(self):
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_ohlc.return_value = (200, SAMPLE_OHLC_BODY_BARS)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote("VNM")
            q.history(start="2024-01-01", interval="1D")
            call_kwargs = mock_client._market.get_ohlc.call_args
            assert call_kwargs[1]["bar_type"] == "STOCK"

    def test_symbol_override(self):
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_ohlc.return_value = (200, SAMPLE_OHLC_BODY_BARS)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote("VNM")
            q.history(symbol="hpg", start="2024-01-01")
            call_kwargs = mock_client._market.get_ohlc.call_args
            assert call_kwargs[1]["query"]["symbol"] == "HPG"
```

### 4.4 Test `intraday()`

```python
class TestDNSEQuoteIntraday:
    def test_returns_dataframe(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "k")
        monkeypatch.setenv("DNSE_API_SECRET", "s")
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_trades.return_value = (200, SAMPLE_TRADES_BODY)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote("VNM")
            df = q.intraday()
            assert isinstance(df, pd.DataFrame)
            assert "price" in df.columns
            assert "volume" in df.columns

    def test_empty_on_none_body(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "k")
        monkeypatch.setenv("DNSE_API_SECRET", "s")
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_trades.return_value = (200, None)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.quote import DNSEQuote
            q = DNSEQuote("VNM")
            df = q.intraday()
            assert df.empty
```

---

## 5. File `tests/unit/explorer/dnse/test_listing.py`

```python
import os
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from tests.unit.explorer.dnse.fixtures import SAMPLE_INSTRUMENTS_BODY, SAMPLE_INSTRUMENTS


class TestDNSEListingInit:
    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("DNSE_API_KEY", raising=False)
        monkeypatch.delenv("DNSE_API_SECRET", raising=False)
        from vnbroker.explorer.dnse.listing import DNSEListing
        with pytest.raises(ValueError, match="DNSE cần api_key"):
            DNSEListing()


def make_listing(instruments_body):
    """Helper: tạo DNSEListing với mock."""
    with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_instruments.return_value = (200, instruments_body)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.listing import DNSEListing
            lst = DNSEListing()
            return lst


class TestDNSEListingAllSymbols:
    def test_returns_dataframe(self):
        lst = make_listing(SAMPLE_INSTRUMENTS_BODY)
        df = lst.all_symbols()
        assert isinstance(df, pd.DataFrame)

    def test_symbol_column_exists(self):
        lst = make_listing(SAMPLE_INSTRUMENTS_BODY)
        df = lst.all_symbols()
        assert "symbol" in df.columns

    def test_row_count(self):
        lst = make_listing(SAMPLE_INSTRUMENTS_BODY)
        df = lst.all_symbols()
        assert len(df) == len(SAMPLE_INSTRUMENTS)

    def test_empty_on_api_error(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "k")
        monkeypatch.setenv("DNSE_API_SECRET", "s")
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_instruments.side_effect = Exception("timeout")
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.listing import DNSEListing
            lst = DNSEListing()
            df = lst.all_symbols()
            assert df.empty


class TestDNSEListingSymbolsByExchange:
    def test_all_exchange_passes_none(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "k")
        monkeypatch.setenv("DNSE_API_SECRET", "s")
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_instruments.return_value = (200, SAMPLE_INSTRUMENTS_BODY)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.listing import DNSEListing
            lst = DNSEListing()
            lst.symbols_by_exchange("ALL")
            call_kwargs = mock_client._market.get_instruments.call_args[1]
            assert call_kwargs.get("market_id") is None

    def test_hose_exchange_passes_hose(self, monkeypatch):
        monkeypatch.setenv("DNSE_API_KEY", "k")
        monkeypatch.setenv("DNSE_API_SECRET", "s")
        with patch("vnbroker.connector.dnse.client.DNSEClient") as MockClient:
            mock_client = MagicMock()
            mock_client._market.get_instruments.return_value = (200, SAMPLE_INSTRUMENTS_BODY)
            MockClient.return_value = mock_client
            from vnbroker.explorer.dnse.listing import DNSEListing
            lst = DNSEListing()
            lst.symbols_by_exchange("hose")   # lowercase test
            call_kwargs = mock_client._market.get_instruments.call_args[1]
            assert call_kwargs.get("market_id") == "HOSE"
```

---

## 6. File `tests/integration/test_dnse_explorer.py`

```python
"""
Integration tests cho DNSE Explorer.
Skip tự động nếu không có DNSE_API_KEY và DNSE_API_SECRET trong môi trường.
"""
import os
import pytest
import pandas as pd

SKIP_REASON = "DNSE_API_KEY hoặc DNSE_API_SECRET không có trong môi trường"

pytestmark = pytest.mark.skipif(
    not os.environ.get("DNSE_API_KEY") or not os.environ.get("DNSE_API_SECRET"),
    reason=SKIP_REASON,
)


@pytest.fixture(scope="module")
def dnse_quote():
    from vnbroker.explorer.dnse.quote import DNSEQuote
    return DNSEQuote("VNM")


@pytest.fixture(scope="module")
def dnse_listing():
    from vnbroker.explorer.dnse.listing import DNSEListing
    return DNSEListing()


class TestDNSEQuoteIntegration:
    def test_history_returns_dataframe(self, dnse_quote):
        df = dnse_quote.history(start="2024-01-01", end="2024-01-31")
        assert isinstance(df, pd.DataFrame), "Phải trả DataFrame"
        assert not df.empty, "Phải có dữ liệu cho tháng 1/2024"

    def test_history_schema(self, dnse_quote):
        df = dnse_quote.history(start="2024-01-01", end="2024-01-05")
        for col in ("time","open","high","low","close","volume"):
            assert col in df.columns, f"Thiếu cột: {col}"

    def test_history_dtypes(self, dnse_quote):
        df = dnse_quote.history(start="2024-01-01", end="2024-01-05")
        assert df["time"].dtype == "datetime64[ns]"
        assert df["open"].dtype == "float64"
        assert str(df["volume"].dtype) == "Int64"

    def test_history_sorted(self, dnse_quote):
        df = dnse_quote.history(start="2024-01-01", end="2024-01-10")
        assert df["time"].is_monotonic_increasing, "Phải tăng dần theo time"

    def test_intraday_returns_dataframe(self, dnse_quote):
        df = dnse_quote.intraday(page_size=50)
        assert isinstance(df, pd.DataFrame)
        # Không assert not empty — thị trường có thể đóng cửa

    def test_history_interval_weekly(self, dnse_quote):
        df = dnse_quote.history(start="2024-01-01", end="2024-03-31", interval="1W")
        assert isinstance(df, pd.DataFrame)


class TestDNSEListingIntegration:
    def test_all_symbols_returns_dataframe(self, dnse_listing):
        df = dnse_listing.all_symbols()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty, "Phải có ít nhất 1 mã chứng khoán"

    def test_all_symbols_has_symbol_column(self, dnse_listing):
        df = dnse_listing.all_symbols()
        assert "symbol" in df.columns

    def test_symbols_by_exchange_hose(self, dnse_listing):
        df = dnse_listing.symbols_by_exchange("HOSE")
        assert isinstance(df, pd.DataFrame)

    def test_symbols_count_reasonable(self, dnse_listing):
        df = dnse_listing.all_symbols()
        assert len(df) > 10, "Ít nhất phải có 10 mã"
```

---

## 7. Lệnh chạy test

```powershell
# Active venv trước
cd "C:\Mujoco Projects\vnbroker-main"
.\.venv\Scripts\Activate.ps1

# Unit tests explorer/dnse (không cần API key)
pytest tests/unit/explorer/dnse/ -v

# Unit tests connector/dnse (đã có sẵn)
pytest tests/unit/connector/dnse/ -v

# Toàn bộ unit tests DNSE
pytest tests/unit/explorer/dnse/ tests/unit/connector/dnse/ -v

# Integration tests (cần env var)
$env:DNSE_API_KEY="your_key"
$env:DNSE_API_SECRET="your_secret"
pytest tests/integration/test_dnse_explorer.py -v

# Full suite với coverage
pytest tests/unit/explorer/dnse/ tests/unit/connector/dnse/ `
       tests/integration/test_dnse_explorer.py `
       --cov=vnbroker/explorer/dnse `
       --cov=vnbroker/connector/dnse `
       --cov-report=term-missing -v
```

---

## 8. KPI pass/fail

| Metric | Ngưỡng bắt buộc | Ghi chú |
|---|---|---|
| Unit test pass rate | 100% | 0 failure được phép |
| Integration pass rate | ≥ 95% nếu có env | Cho phép skip, không cho phép error |
| Coverage `explorer/dnse/` | ≥ 80% | Đo bằng `--cov` |
| Thời gian unit suite | ≤ 30 giây | Không gọi mạng thật |
| Không có `DeprecationWarning` mới | 100% | Không tạo thêm warning |

---

## 9. Acceptance gate (QA sign-off)

Trước khi merge, QA chạy lệnh này và paste output vào PR:

```powershell
pytest tests/unit/explorer/dnse/ tests/unit/connector/dnse/ -v `
       --tb=short 2>&1 | Tee-Object -FilePath "dnse_unit_test_result.txt"
cat dnse_unit_test_result.txt
```

Output phải kết thúc bằng dòng: `X passed, 0 failed`.
