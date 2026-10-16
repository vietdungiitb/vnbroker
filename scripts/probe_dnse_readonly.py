"""Probe read-only DNSE OpenAPI production (không VPN) — bằng chứng tái lập.

Chạy:
    .venv\\Scripts\\python.exe scripts\\probe_dnse_readonly.py

Đọc `DNSE_API_KEY` / `DNSE_API_SECRET` từ môi trường (hoặc `.env`).
KHÔNG in credential. KHÔNG gửi lệnh thật — chỉ GET + dry-run envelope.

Kết quả 2026-10-16 (không VPN) ghi tại `docs/REPORT_DNSE_LIVE_20261016.md`
§8-10 và kế hoạch fix tại `docs/PLAN_DNSE_FIX_20261016.md`.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

if not os.getenv("DNSE_API_KEY"):
    _env = _REPO / ".env"
    if _env.exists():
        for _raw in _env.read_text(encoding="utf-8").splitlines():
            _line = _raw.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from vnbroker.connector.dnse.client import DNSEClient  # noqa: E402
from vnbroker.connector.dnse.core.errors import DNSEValidationError  # noqa: E402
from vnbroker.connector.dnse.constants import BOARD_IDS, MARKET_IDS  # noqa: E402
from vnbroker.connector.dnse.core.time_utils import (  # noqa: E402
    VIETNAM_TZ,
    vn_day_bounds,
)

PROD = "https://openapi.dnse.com.vn"
NOW_S = int(time.time())
DAY_S = NOW_S - 86400

_results: list[tuple[str, str, str]] = []


def _vn_day_open() -> int:
    """Nửa đêm theo GIỜ VIỆT NAM của hôm nay.

    Trước đây là `NOW_S - (NOW_S % 86400)` — đó là nửa đêm **UTC**, lệch 7 tiếng
    so với ngày giao dịch. Trong khoảng 00:00–07:00 giờ VN, probe sẽ tưởng
    đang hỏi "cùng ngày" trong khi thật ra là khác ngày. Đây đúng là lỗi lệch
    7 tiếng mà lát A đã sửa ở tầng connector; script verify lại thì lại mang nó
    vào.
    """
    return vn_day_bounds(datetime.now(VIETNAM_TZ))[0]


def _record(name: str, status: str, detail: str) -> None:
    _results.append((name, status, detail))
    print(f"[{status}] {name} — {detail}", flush=True)


def _probe(name: str, fn) -> None:
    try:
        out = fn()
        if hasattr(out, "shape"):
            detail = f"DataFrame shape={out.shape}"
        elif isinstance(out, dict):
            lists = {k: len(v) for k, v in out.items() if isinstance(v, list)}
            detail = f"keys={list(out.keys())[:6]} lists={lists}"
        elif isinstance(out, list):
            detail = f"list len={len(out)}"
        else:
            detail = type(out).__name__
        _record(name, "PASS", detail)
    except Exception as exc:  # noqa: BLE001 — probe ghi mọi lỗi, không nuốt
        code = getattr(exc, "status_code", None)
        _record(name, "FAIL", f"{type(exc).__name__} status={code}: {str(exc)[:120]}")


def _defect_probes(client: DNSEClient, account_no: str) -> None:
    """Probe riêng cho từng defect D2-D11, để bằng chứng tái lập được.

    Trước 2026-10-16 script này **không** probe D1-path/D2/D3/D7/D10/D11 —
    bảng "bằng chứng âm tính" trong `docs/PLAN_DNSE_FIX_20261016.md` vì thế
    không ai tái lập lại được (finding M1/M2 của audit). Ở đây mỗi defect có
    đúng một lệnh.

    Dùng `_market._http` để thấy **status + payload lỗi đầy đủ**: các lỗi quan
    trọng nhất của lát F (`oneof` của `marketId`, `not found boardId`) chỉ nằm
    trong body mà `_resolve_output` không trả về.
    """
    http = client._market._http  # noqa: SLF001 - probe tới chỗ kiểm thật
    today = time.strftime("%Y-%m-%d")

    def raw(name: str, path: str, query: dict | None = None) -> None:
        try:
            status, body = http.request("GET", path, query=query)
            detail = (
                f"status={status} keys={list(body)[:5] if isinstance(body, dict) else type(body).__name__}"
            )
            _record(name, "PASS", detail)
        except Exception as exc:  # noqa: BLE001
            payload = getattr(exc, "payload", None)
            _record(
                name,
                "FAIL",
                f"status={getattr(exc, 'status_code', None)} "
                f"{str(exc)[:90]} | payload={str(payload)[:160]}",
            )

    print("--- D1/D5: hai path từng bị kết luận là 'không tồn tại' ---")
    raw("D1 working-dates", "/market/working-dates")
    raw("D5 corporate-action-history (đúng)", f"/accounts/{account_no}/corporate-action-history")
    raw("D5 corporate-actions (sai, đối chứng)", f"/accounts/{account_no}/corporate-actions")

    print("--- D2: get_orders thiếu pageIndex / pageSize ---")
    base = {"marketType": "STOCK", "orderCategory": "NORMAL"}
    raw("D2 orders KHÔNG phân trang", f"/accounts/{account_no}/orders", base)
    raw("D2 orders có pageIndex", f"/accounts/{account_no}/orders",
        {**base, "pageIndex": 1})
    raw("D2 orders có cả hai", f"/accounts/{account_no}/orders",
        {**base, "pageIndex": 1, "pageSize": 20})
    raw("D2 orders thiếu orderCategory", f"/accounts/{account_no}/orders",
        {"marketType": "STOCK", "pageIndex": 1, "pageSize": 20})

    print("--- D3/D4: order_history from/to ---")
    raw("D3 history thiếu cả hai", f"/accounts/{account_no}/orders/history", {"marketType": "STOCK"})
    raw("D3 history chỉ from", f"/accounts/{account_no}/orders/history", {"marketType": "STOCK", "from": "2026-10-01"})
    raw("D4 history đủ from+to", f"/accounts/{account_no}/orders/history", {"marketType": "STOCK", "from": "2026-10-01", "to": today})

    print("--- D6: position_id không phải số ---")
    raw("D6 positions/1 (số, id tồn tại)", "/positions/1", {"marketType": "STOCK"})
    raw("D6 positions/fake (rác)", "/positions/fake", {"marketType": "STOCK"})
    raw("D6 positions/999999 (biên quyền?)", "/positions/999999", {"marketType": "STOCK"})

    print("--- D7: volume profile time format + boardId ---")
    raw("D7 time=1700 (int)", "/price/HPG/trades/volume-profile", {"time": 1700})
    raw("D7 time=ngày, thiếu boardId", "/price/HPG/trades/volume-profile", {"time": today})
    raw("D7 time=ngày + boardId=G1 (giá trị thật)", "/price/HPG/trades/volume-profile",
        {"time": today, "boardId": "G1"})

    print("--- D8: from/to là GIÂY chứ không phải ms ---")
    raw("D8 quotes to=bây giờ (giây)", "/price/HPG/quotes", {"from": NOW_S - 86400, "to": NOW_S, "limit": 5})
    raw("D8 quotes to=bây giờ (ms)", "/price/HPG/quotes", {"from": (NOW_S - 86400) * 1000, "to": NOW_S * 1000, "limit": 5})

    print("--- D9: market_index cùng ngày / khác ngày ---")
    # Ngày theo GIỜ VN, không phải nửa đêm UTC: dùng `vn_day_bounds` để lát
    # verify lại không tự tái tạo đúng lỗi lệch 7 tiếng mà lát A đã sửa.
    day_open, day_close = vn_day_bounds(datetime.now(VIETNAM_TZ))
    raw("D9 cùng ngày", "/price/VNINDEX/market-index", {"from": day_open, "to": min(day_close, NOW_S)})
    raw("D9 khác ngày", "/price/VNINDEX/market-index", {"from": day_open - 86400, "to": NOW_S})

    print("--- D10/D11: từ điển boardId/marketId ---")
    # Đọc từ điển server tự trả về TRƯỚC, thay vì đoán: /instruments có cột
    # `marketId`. Đây là cách đã thắng: 24 giá trị đoán đều thất bại, còn đọc
    # response thì ra ngay tập thật (L-R04).
    raw("D11 instruments (đọc cột marketId)", "/instruments", {"limit": 200})
    for market_id in sorted(MARKET_IDS):
        raw(f"D11 marketId={market_id}", "/instruments", {"marketId": market_id, "limit": 3})
    for board_id in sorted(BOARD_IDS):
        raw(f"D10 secdef boardId={board_id}", "/price/HPG/secdef", {"boardId": board_id})
    # Vẫn thử vài giá trị sai để ghi lại hành vi từ chối của server.
    for wrong in ("HOSE", "G0", "G9"):
        raw(f"D10 secdef boardId={wrong} (kỳ vọng lỗi)", "/price/HPG/secdef", {"boardId": wrong})


def main() -> int:
    client = DNSEClient(
        api_key=os.environ["DNSE_API_KEY"],
        api_secret=os.environ["DNSE_API_SECRET"],
        base_url=PROD,
        timeout_seconds=20.0,
    )

    print("=" * 70)
    print("DNSE production read-only probe (API key HMAC, không OTP)")
    print("=" * 70)

    accounts = client.get_accounts(raw=True)
    account_no = accounts["accounts"][0].get("accountNo") or accounts["accounts"][0].get("id", "")
    print(f"  account_no = {account_no}")

    _probe("get_balances", lambda: client.get_balances(account_no, raw=True))
    _probe("get_positions(STOCK)", lambda: client.get_positions(account_no, "STOCK", raw=True))
    _probe("get_loan_packages(HPG)", lambda: client.get_loan_packages(account_no, "STOCK", symbol="HPG", raw=True))
    _probe("get_loans(STOCK)", lambda: client.get_loans(account_no, "STOCK", raw=True))
    _probe("get_ppse(HPG,25000)", lambda: client.get_ppse(account_no, "STOCK", "HPG", 25000, 0, raw=True))
    _probe("get_orders(STOCK,NORMAL)", lambda: client.get_orders(account_no, "STOCK", "NORMAL", raw=True))
    _probe("get_order_history", lambda: client.get_order_history(account_no, "STOCK", from_date="2026-10-01", to_date="2026-10-16", raw=True))
    _probe("get_corporate_action_history", lambda: client.get_corporate_action_history(account_no, "STOCK", raw=True))
    # `position_id="fake"` giờ bị chặn ở CLIENT ⇒ đây là **PASS**, không phải
    # FAIL. Nhãn FAIL của `_probe` dành cho "server trả lỗi"; còn đây là "vnbroker
    # không gửi đi", đúng thứ ta muốn. Ghi riêng để không đọc nhầm.
    try:
        client.get_position_by_id("STOCK", "fake", raw=True)
        _record("get_position_by_id(fake)", "FAIL",
                "D6 CHƯA chặn — vnbroker đã gửi id rác, server sẽ trả 500")
    except DNSEValidationError as exc:
        _record("get_position_by_id(fake)", "PASS",
                f"D6 đã chặn client-side: {exc.error_code}")
    except Exception as exc:  # noqa: BLE001
        _record("get_position_by_id(fake)", "FAIL",
                f"sai loại lỗi: {type(exc).__name__}: {str(exc)[:100]}")

    _probe("get_security_definition(HPG)", lambda: client.get_security_definition("HPG", raw=True))
    _probe("get_instruments(HPG)", lambda: client.get_instruments(symbol="HPG", limit=5, raw=True))
    _probe("get_latest_quote(HPG)", lambda: client.get_latest_quote("HPG", raw=True))
    _probe("get_latest_trade(HPG)", lambda: client.get_latest_trade("HPG", raw=True))
    _probe("get_close_price(HPG)", lambda: client.get_close_price("HPG", raw=True))
    _probe("get_quotes(HPG, sec)", lambda: client.get_quotes("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_trades(HPG, sec)", lambda: client.get_trades("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_expected_price(HPG, sec)", lambda: client.get_expected_price("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_foreign_trading(HPG, sec)", lambda: client.get_foreign_trading("HPG", from_date=DAY_S, to_date=NOW_S, limit=5, raw=True))
    _probe("get_market_index(VNINDEX, same day)", lambda: client.get_market_index("VNINDEX", from_date=_vn_day_open(), to_date=NOW_S, limit=5, raw=True))
    _probe("get_ohlc(1D, HPG)", lambda: client.get_ohlc("1D", query={"symbol": "HPG", "from": DAY_S, "to": NOW_S, "limit": 5}, raw=True))

    # --- Working dates (D1) -------------------------------------------------
    # Đính chính 2026-10-16: comment cũ ghi "Server không có endpoint
    # working-dates" và coi None là FAIL. Đo lại **không VPN**: path
    # `/market/working-dates` trả **200**, 257 `workingDates`. Method đã được
    # sửa ở `services/market_service.get_working_dates` sang path thật.
    # Nay `None` vẫn là FAIL — nhưng vì lý do khác: không có request nào đi ra
    # hoặc server không trả danh sách.
    wd = client.get_working_dates(raw=True)
    if wd is None:
        _record("get_working_dates", "FAIL", "D1: vẫn trả None — method chưa gọi network")
    else:
        count = len(wd.get("workingDates", [])) if isinstance(wd, dict) else "?"
        _record("get_working_dates", "PASS", f"keys={list(wd)[:4] if isinstance(wd, dict) else type(wd).__name__} count={count}")

    print()
    _defect_probes(client, account_no)
    print()
    print("=" * 70)
    passed = sum(1 for _, s, _ in _results if s == "PASS")
    print(f"SUMMARY: PASS={passed} FAIL={len(_results) - passed} TOTAL={len(_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
