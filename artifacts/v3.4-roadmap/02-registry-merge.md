# ISSUE-02 — Gộp BrokerRegistry (2-3 ngày, dọn nợ kiến trúc)

## Background
- `vnbroker/common/client.py:230-261 Vnbroker.broker()` đang `register` mỗi lần gọi:
  `if not BrokerRegistry.is_registered("tcbs"): register(...)` + tương tự `"ssi"` — không thread-safe, sai trách nhiệm (lookup lẫn registration).
- `vnbroker/broker/registry.py:11-88 BrokerRegistry` là singleton nhưng `_providers` là class-dict, `register/get/create` đều là classmethod không lock.
- `vnbroker/core/unified_registry.py:48-95` đã có `list_brokers()/get_broker()` nhưng chỉ proxy về `BrokerRegistry`, chưa phải single entry point thật.
- Lưu ý: `client.py:254` vẫn import `SSIBrokerClient` trong khi TODO v3.1.1 ghi đã xóa `broker/ssi/` — cần xác minh cây thư mục thực tế trước khi sửa (nếu đã xóa thì bỏ nhánh ssi khỏi registry).

## Scope
1. Chuyển `BrokerRegistry.register` sang **register 1 lần ở import** (`vnbroker/broker/tcbs/__init__.py` hoặc `vnbroker/broker/__init__.py`), xóa logic register-lazy trong `Vnbroker.broker()`.
2. Thêm `threading.Lock` cho `register/get/create/clear`.
3. Đưa broker lookup vào `UnifiedRegistry` (`get_broker/list_brokers/is_broker_registered`) và đổi `Vnbroker.broker()` sang gọi `UnifiedRegistry` thay vì `BrokerRegistry` trực tiếp.
4. Không đổi auth flow, không đổi constructor kwargs.

## File chạm cụ thể
- `vnbroker/common/client.py:230-261`
- `vnbroker/broker/registry.py:11-88`
- `vnbroker/broker/__init__.py`, `vnbroker/broker/tcbs/__init__.py` (điểm register 1 lần)
- `vnbroker/core/unified_registry.py:48-95,102-109`
- Test registry hiện tại (tìm trong `tests/unit/broker/` + `tests/unit/core/test_*registry*`)

## DoD
- [ ] `ruff` sạch, test registry hiện tại xanh.
- [ ] Không còn `register` trong `Vnbroker.broker()`; gọi 2 lần liên tiếp trả về đúng class mà không re-register.
- [ ] Thread-safety: test đơn giản spawn 2 thread register/get không race.
- [ ] Auth flow giữ nguyên (OTP/API key path không đổi).

Effort: 2-3 ngày. Dependency: sau ISSUE-01 (để không xung đột `common/client.py` nếu làm song song).
