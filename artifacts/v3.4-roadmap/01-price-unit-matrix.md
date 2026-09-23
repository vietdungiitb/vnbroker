# ISSUE-01 — Price-unit matrix test (làm TRƯỚC, 1-2 ngày, unblock DNSE/VCI)

## Background
- Điểm trung tâm đã có: `vnbroker/core/utils/transform.py:66 normalize_price_columns()` + `_resolve_target_price_unit()` (default VND, env `vnbroker_PRICE_UNIT`).
- Normalize đang rải rác: `explorer/vci/quote.py:324,543,663,674,688`, `explorer/kbs/quote.py:489,698`, `explorer/kbs/trading.py:224,233`, `explorer/tcbs/trading.py:109,130`, `explorer/vci/trading.py:133`.
- Ngoại lệ: `explorer/tcbs/quote.py:533-542 _compute_ohlc_from_intraday` tự set `source_unit` theo `asset_type` (index/derivative dùng target unit) — dễ sai khi so sánh chéo.
- `explorer/dnse/*` trả raw, chưa qua normalize thống nhất.
- Test hiện tại thiếu: `tests/unit/api/test_quote_price_unit_consistency.py` chỉ cover VCI/KBS/TCBS history stock; chưa có DNSE, chưa có index/derivative; `tests/unit/core/test_price_unit_normalization.py` chỉ test unit hàm lẻ.

## Scope
1. Gộp mọi normalize về 1 điểm `transform.normalize_price_columns`; xóa normalize tự phát ở `TCBSQuote`/`DNSEQuote` (chỉ truyền đúng `source_unit`, để hàm trung tâm quyết `target_unit`).
2. Thêm test matrix **4 providers (VCI/KBS/TCBS/DNSE) x stock/index/derivative** assert cùng đơn vị VND (`df.attrs["price_unit"]`) và cùng giá trị `close` (mock `send_request` như test hiện tại, mở rộng thêm mock DNSE + index/derivative payload).
3. Không đổi behavior live: chỉ refactor đường đi, giữ nguyên `source_unit='VND'` đầu vào hiện tại.

## File chạm cụ thể
- `vnbroker/core/utils/transform.py:66-99`
- `vnbroker/explorer/tcbs/quote.py:533-542`
- `vnbroker/explorer/dnse/quote.py` (bổ sung normalize)
- `vnbroker/explorer/vci/quote.py`, `vnbroker/explorer/kbs/quote.py`
- `vnbroker/explorer/vci/trading.py:133`, `vnbroker/explorer/kbs/trading.py:224-236`, `vnbroker/explorer/tcbs/trading.py:109-133`
- `tests/unit/api/test_quote_price_unit_consistency.py:52-100` (mở rộng)
- `tests/unit/core/test_price_unit_normalization.py`, `tests/unit/explorer/test_trading_price_unit_standardization.py`
- Docs: `docs/PRICE_UNIT_API_GUIDE.md`, `docs/AUDIT_REPORT_v3.3.0.md:209-210`

## DoD
- [ ] Test matrix mới đỏ-trước-xanh-sau, cover DNSE + index/derivative.
- [ ] Không còn normalize rải rác ngoài `transform.normalize_price_columns`.
- [ ] `pytest tests/unit -q` 755+ xanh, `ruff` sạch.

Effort: 1-2 ngày. Dependency: không — unblock mọi so sánh giá về sau.
