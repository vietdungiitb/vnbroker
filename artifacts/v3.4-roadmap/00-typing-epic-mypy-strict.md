# ISSUE-00 — Epic typing: dọn `mypy vnbroker --strict` (550 lỗi thực tế)

## Background (evidence, 2026-09-22)
- `python -m mypy vnbroker --strict` → **550 errors** (594 dòng output).
- Phân bố: `no-untyped-def 202`, `type-arg 122`, `no-untyped-call 52`, `no-any-return 12`, còn lại `assignment/attr-defined/import-untyped/valid-type`.
- Top file: `broker/tcbs/account.py 82` + `broker/tcbs/market.py 22` = 104; `connector/dnse/client.py 31`, `core/utils/upgrade.py 29`, `bot/notify.py 22`, `core/utils/parser.py 21`, `base.py 19`, `core/types.py 18`, `explorer/tcbs/websocket.py 17`, `connector/dnse/core/errors.py 15`.
- `pandas-stubs 3.0.5` đã cài → lỗi Protocol/Series là misuse, không phải thiếu stub.
- Config hiện tại chỉ ở `pyproject.toml.testing:[tool.mypy]` (non-strict, ignore `explorer.*`, `connector.*`). `pyproject.toml` chính chưa có `[tool.mypy]`.
- Baseline test: `pytest tests/unit --collect-only` → 755 tests.

## Scope (không bật strict 1 phát)
1. Thêm per-module override trong `pyproject.toml:[tool.mypy]`: module sạch (`config`, `cache`, `indicators`, `normalize`) bật `strict=True` trước để giữ xanh; `broker.*`, `connector.dnse.*` ở `ignore_errors=False` dần dần.
2. Fix theo thứ tự:
   - (a) Cơ học (<1 ngày): `var-annotated` (`core/utils/browser_profiles.py:110 USER_AGENTS`, `core/utils/deprecation.py:23 _registry`, `core/registry.py:115 result`, `core/utils/upgrade.py:70 warnings_list`), `implicit Optional` (`reference_date=None`, `agg_rules=None`), `type-arg` (`dict`, `list`, `Type`, `Callable`, `TTLCache` thiếu tham số).
   - (b) Websocket (2-3 file): `explorer/tcbs/websocket.py:86 self._ws = None` → `Optional[ClientConnection]` + `guard if self._ws is None: raise` trước mọi `send/recv`.
   - (c) Broker return types: `broker/tcbs/account.py:69-73 get_profile() -> Union[DataFrame, dict]`, `broker/tcbs/market.py` tương tự — quyết 1 contract (raw dict hay DataFrame), sửa annotation + test tương ứng.
   - (d) Pandas Protocol cuối: `core/types.py:10-19 Protocol`, `core/utils/compat.py`, `core/utils/transform.py` (`Series not callable`, `valid-type`) — thử `typing_extensions.Protocol` hoặc fix stub usage, không pin bừa.

## File chạm cụ thể
- `pyproject.toml` (thêm `[tool.mypy]` + overrides)
- `vnbroker/broker/tcbs/account.py`, `vnbroker/broker/tcbs/market.py`
- `vnbroker/explorer/tcbs/websocket.py:86`
- `vnbroker/core/types.py`, `vnbroker/core/utils/compat.py`, `vnbroker/core/utils/transform.py`
- `vnbroker/core/utils/browser_profiles.py:110`, `vnbroker/core/utils/deprecation.py:23`, `vnbroker/core/registry.py:115`, `vnbroker/connector/dnse/core/errors.py:58-66`
- `vnbroker/broker/base.py:73`, `vnbroker/broker/registry.py:61`, `vnbroker/broker/session.py:54`

## DoD
- [ ] `mypy vnbroker --strict` không còn lỗi **mới** so với baseline đã ghi (cho phép legacy-exclude list có ngày hết hạn).
- [ ] CI fail khi PR thêm lỗi mới.
- [ ] `pytest tests/unit` 755 xanh, `ruff` 0 lỗi mới.
- [ ] Không yêu cầu 0 tuyệt đối ngay.

## Gates mỗi PR
`ruff check` → `pytest tests/unit -q` → `mypy` diff vs baseline. Mỗi module 1 PR nhỏ để dễ revert.

Effort: ~3-5 ngày. Rủi ro thấp nếu làm từng module.
