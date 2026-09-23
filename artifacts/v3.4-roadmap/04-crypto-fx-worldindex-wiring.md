# ISSUE-04 — FX/Crypto/WorldIndex wiring (lớn nhất, 1-2 tuần, tách PR riêng)

## Background
- `vnbroker/common/client.py:139-194` hiện cả 3 method `fx()/crypto()/world_index()` đều `raise NotImplementedError` (đúng theo cleanup v3.1.1 — MSN/FMP đã xóa).
- `vnbroker/connector/binance/__init__.py` **0 dòng** — chưa có implementation nào để wiring.
- Chưa quyết nguồn cho FX/WorldIndex (Yahoo/TwelveData?): cần quyết key, quota, cache trước khi code.

## Scope (tách PR, crypto trước)
- **PR-1 crypto (v3.4, dễ nhất):** implement `connector/binance/` (client `klines`/`ticker` public, không auth) → wiring `Vnbroker.crypto(symbol, source="BINANCE")` trả DataFrame chuẩn (`time/open/high/low/close/volume`, `attrs[price_unit]`); unit mock + 1 live smoke gated env (`vnbroker_RUN_LIVE_INTEGRATION=1`).
- **PR-2 fx/world_index (v3.5):** quyết provider (đề xuất Yahoo public trước, TwelveData nếu cần key) → cùng interface `history/intraday` chuẩn; cache + quota doc.

## File chạm cụ thể
- `vnbroker/common/client.py:139-194` (bỏ NotImplementedError từng method theo PR)
- `vnbroker/connector/binance/__init__.py` + file mới `vnbroker/connector/binance/client.py`
- Mới: `vnbroker/explorer/binance/` hoặc reuse connector trực tiếp (quyết ở PR-1, ghi vào PR description)
- Test: `tests/unit/connector/test_binance_*.py` (mock) + `tests/integration/...` (live smoke gated)
- Docs: `README.md`, `TODO.md:19` (bỏ dòng FX/Crypto future khi xong), `docs/` guide mới nếu có provider mới.

## DoD mỗi provider
- [ ] Interface `history/intraday` chuẩn, đơn vị/giá documented.
- [ ] Unit mock xanh + 1 live smoke gated env xanh (skip mặc định khi không có env).
- [ ] Docs cập nhật (nguồn, key/quota/cache).
- [ ] Không gộp crypto+fx+index chung 1 PR để dễ revert.

## Gates chung
Mỗi PR: `ruff 0`, `pytest tests/unit 755+ xanh`, `mypy không thêm lỗi mới` (theo baseline ISSUE-00).

Effort: crypto 3-5 ngày; fx/index 1 tuần (tùy quyết provider). Dependency: sau ISSUE-01 (reuse chuẩn price-unit) và ISSUE-00 (không thêm nợ typing mới).
