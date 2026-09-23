# ISSUE-03 — Circuit-breaker persistent cho source_router (3-5 ngày)

## Background
- `vnbroker/core/source_router.py:1-213` hiện là dict memory: `_health_state: Dict[Tuple[str,str], Dict[str,float]]` + `_health_lock`, cooldown exp-backoff `5s,10s,20s,40s,max 90s` ở `record_failure():138-147`.
- `get_source_health_snapshot():150-170` đã expose metric nhưng **mất state khi restart**; chưa có half-open probe (chỉ có healthy/unhealthy theo `cooldown_until`).
- `OPEN_SOURCE_CANDIDATES:22-29` và `PRIMARY_SOURCE_POOLS:36-43` (quote→vci, trading→kbs) giữ nguyên, không sửa trong issue này.

## Scope
1. Thay `_health_state` dict thuần bằng **store có persist**: interface `HealthStore` với 2 backend `SQLiteHealthStore` (mặc định, file local) + `MemoryHealthStore` (fallback), optional Redis nếu đã có dependency (không thêm dep mới nếu chưa có).
2. Thêm trạng thái half-open: sau khi hết cooldown, cho 1 probe request qua; `record_success` → close, `record_failure` → mở lại với backoff.
3. Expose `health(module) -> snapshot` (tái dùng `get_source_health_snapshot`) + metric `failures/in_cooldown/cooldown_remaining_sec/last_success_age/last_failure_age`.
4. Giữ API cũ (`build_source_order/record_success/record_failure/should_failover/annotate_result_source/reset_router_state`) tương thích ngược.

## File chạm cụ thể
- `vnbroker/core/source_router.py:45-47,82-85,129-170,210-213`
- File mới: `vnbroker/core/health_store.py` (interface + sqlite + memory)
- Test mới: `tests/unit/core/test_source_router_circuit_breaker.py` (giả lập fail→cooldown→half-open→recover; giả lập restart vẫn giữ state với sqlite backend)
- Không chạm: `OPEN_SOURCE_CANDIDATES`, `PRIMARY_SOURCE_POOLS`, per-module explorer code.

## DoD
- [ ] Restart process không mất state (test với sqlite file tmp).
- [ ] Test `fail → cooldown → half-open probe → recover` xanh.
- [ ] `pytest tests/unit -q` xanh, `ruff` sạch, không đổi thứ tự ưu tiên provider hiện tại.

Effort: 3-5 ngày. Dependency: sau ISSUE-02 (đều chạm `core/`).
