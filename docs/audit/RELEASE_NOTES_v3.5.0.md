# v3.5.0 — Kiến trúc hai tầng + an toàn đường giao dịch

7 commit · 59 file · +5123 / −825

Bản này là **breaking + feature**, không phải patch. Đọc mục Breaking trước khi nâng cấp.

---

## ⚠️ Breaking changes

### 1. `history()` qua `Vnbroker` trả `time` dạng tz-aware

Cột `time` giờ là **tz-aware** (`Asia/Ho_Chi_Minh`) thay vì tz-naive, và kết quả được **lọc theo `start`/`end`**.

**Lý do:** các provider trả timezone khác nhau — VCI tz-aware, KBS/DNSE/SSI tz-naive — nên `pd.concat` giữa hai provider sinh **dtype `object`**, phá mọi phép tính thời gian phía downstream mà **không ném exception**. Riêng VCI còn trả nến **ngoài khoảng `start`/`end`** yêu cầu mà không báo lỗi.

```python
# trước
df["time"] >= pd.Timestamp("2024-01-01")           # giờ TypeError: tz-naive vs tz-aware

# sau
df["time"] >= pd.Timestamp("2024-01-01", tz="Asia/Ho_Chi_Minh")
# hoặc nếu cần giữ hành vi cũ:
df["time"].dt.tz_localize(None)
```

Gọi provider trực tiếp (`VCIQuote(...).history()`) **không đổi** — chỉ đường qua `Vnbroker` bị chuẩn hoá.

### 2. `connector/dnse` yêu cầu `enable_write()`

Bốn hàm ghi tiền/lệnh nay có `dry_run=True` mặc định và cần bật quyền trước:

- `place_order`
- `cancel_order`
- `deposit_derivative_margin`  ← nạp tiền thật
- `withdraw_derivative_margin` ← rút tiền thật

```python
trade = Trade(...)
result = trade.place_order(...)        # dry_run=True → KHÔNG gửi, trả envelope

trade.enable_write()                   # bật quyền gửi thật (mặc định TẮT)
trade.place_order(..., dry_run=False)  # mới thực sự gửi
```

`dry_run=False` mà chưa `enable_write()` sẽ ném `BrokerPermissionError`.

**Lý do:** trước đây các hàm này **không có** `dry_run`, **không có** `write_gate` — gửi thật ngay lập tức, kể cả nạp/rút ký quỹ.

### 3. SSI không retry tự động trên POST đặt lệnh

`SSIHttpClient` trước đây bọc **mọi** method trong retry không phân biệt idempotent. `ConnectionError` xảy ra cả khi server **đã nhận xong lệnh** nhưng response bị mất → gửi lại lệnh trùng.

**Đã tái hiện được: 1 lời gọi → 5 POST thật** (`max_retries=5`), và caller nhận về `{'orderStatus': 'NEW'}` không có dấu hiệu trùng.

Nay chỉ retry method idempotent (`GET`/`HEAD`/`PUT`/`DELETE`/`OPTIONS`). Với POST, lỗi được ném ra kèm `code="NETWORK_ERROR_NON_IDEMPOTENT"`.

**Cách đặt lại an toàn:** truyền `clientRequestId` cố định. Khi lỗi mạng xảy ra, key đó được gắn vào exception nên bạn dùng lại được:

```python
try:
    vn.broker(provider="ssi").place_order(..., request_id="my-fixed-key-123")
except BrokerNetworkError as e:
    key = getattr(e, "client_request_id", None)   # tái sử dụng key này
```

---

## ✨ Tính năng mới

### Tầng 1 — dữ liệu ẩn danh, không cần biết provider

```python
from vnbroker.ui.market import Market

mkt = Market(auto=True)                       # tự chọn + tự xoay vòng provider
hist = mkt.equity("ACB").history(start="2026-01-01", end="2026-06-30")

# hoặc
from vnbroker import Vnbroker
vn = Vnbroker(source="AUTO")
```

Hệ thống tự ưu tiên provider ổn định và xoay vòng khi gặp rate-limit / mất kết nối, dùng cơ chế health store có cooldown, exponential backoff và half-open probe.

- Failover áp cho `history`, `intraday`, `price_depth`
- Kết quả có `df.attrs["source_used"]` để biết provider nào đã phục vụ
- Provider mặc định của pool tầng 1: **VCI, KBS** (không cần auth)
- **Mặc định vẫn là `"KBS"`** — `auto=True` là tuỳ chọn, không phải mặc định

**Hết provider thì ném lỗi gốc, không bao giờ trả DataFrame rỗng** — frame rỗng khiến người dùng tưởng "hôm nay không giao dịch" thay vì "đã lỗi mạng".

### Tầng 2 — broker, chọn provider tường minh

```python
vn.broker(provider="ssi").get_balance()
vn.broker(provider="tcbs").get_balance()
```

Mỗi broker giữ đúng khung OpenAPI riêng (SSI: RSA + ConsumerID + IP cố định; TCBS: API Key + OTP; DNSE: HMAC). Cố ép chúng vào một interface chung sẽ tạo ra interface rỗng kiểu `**kwargs`.

### Chuẩn hoá dữ liệu ở một điểm duy nhất

`_normalize_quote_result()` trong `common/data.py` là **điểm kiểm soát duy nhất**: tz-aware, lọc biên, sort, không mutate frame của provider. Provider mới thêm vào tự động tuân thủ mà không cần sửa ở từng provider.

### `match_type` chuẩn hoá

Trước đây mỗi provider một cách viết (VCI `'b'`, TCBS `'BU'`, KBS `'B'`) và **DNSE/SSI không có nhánh nào** nên giữ nguyên giá trị provider — khiến `df[df.match_type == "Buy"]` cho kết quả khác nhau tuỳ provider, sai mà không báo lỗi. Nay chỉ còn `Buy` / `Sell` / `unknown`.

### `Redactor.redact_url()`

Client HMAC (DNSE, KBS) truyền credential trong query string kiểu `?api_key=...&signature=...`. `connector/dnse/websocket.py` trước đây log URL nguyên văn ở level `INFO`. Nay đã redact.

---

## 🐛 Sửa hạ tầng

- **CI không chạy cho PR vào `dev`.** Cả 4 workflow trigger `[main, develop]` nhưng repo không có branch `develop` — mọi PR vào `dev` chạy không CI gì. Đã đổi thành `[main, dev]`.
- **Các gate thật sự chặn.** `pytest tests/contract/` và `ruff` chạy **không** `continue-on-error`. Trước đó mọi bước lint/type/security đều advisory.
- **`ruff` có mặt trong CI lần đầu.** Trước đó không có trong CI và không có `[tool.ruff]` — 2888 lỗi tồn tại mà không ai chặn. Rule set nay nhỏ và có chủ đích: **2888 → 0**.
- **`check_version_sync.py` quét cả `tests/`.** Trước đó gate xanh trong khi 3 test đỏ, vì test hardcode version cũ.
- **Reset baseline `mypy --strict`.** File ghi 556 dòng nhưng thực tế có **1266** lỗi → gate luôn đỏ, không bảo vệ được gì. Đã reset về trạng thái thật kèm **hạn 2026-11-01**, và hạn **được thực thi** (`baseline_is_expired`).
- **3 bug `B006` thật.** `params: Dict = {...}` dùng chung giữa các lần gọi ở 3 `explorer/*/screener.py` (rò trạng thái).
- **Xoá `vnbroker/core/base/`** — 164 câu lệnh code chết. Đây là registry thứ hai, đã bị `core/registry.py` thay thế từ `dbcd81a` ("registry merge") nhưng quên dọn. 0% coverage và không module nào import. Bằng chứng hoạt động lưu ở `f5de70d`; `tests/unit/core/test_legacy_base_module.py` nay là gate ngăn tái sinh.

---

## 📊 Số liệu

| | |
|:---|:---|
| pytest | **1001 passed**, 5 skipped, 0 failed |
| ruff | 0 lỗi |
| version-sync | OK 3.5.0 |
| mypy baseline | OK (hạn 2026-11-01) |
| coverage | 55% |

Contract test mới ở `tests/contract/` khoá hợp đồng tầng 1: mọi provider ẩn danh phải trả cùng schema, và failover phải xoay vòng đúng.

---

## 📚 Tài liệu

Báo cáo audit đầy đủ và kế hoạch hiệu chỉnh kiến trúc nằm ở `docs/audit/`:

| File | Nội dung |
|:---|:---|
| `AUDIT_REPORT_2026-10-01.md` | Báo cáo audit toàn bộ codebase (51K LOC) |
| `KIEN_TRUC_HAI_TANG_PLAN.md` | Kế hoạch 4 giai đoạn + kết quả từng bước |
| `S2_EXPLORER.md` | Audit 5 provider dữ liệu thị trường |
| `S3_BROKER.md` | Audit đường broker (auth, ký, đặt lệnh, WebSocket) |

---

## Nâng cấp

```bash
pip install -U vnbroker==3.5.0
```

Nếu bạn dùng `history()` qua `Vnbroker` và so `df["time"]` với timestamp naive, hãy xem Breaking #1.

Thư viện sẽ tự hiện cảnh báo khi bạn chạy trên phiên bản cũ — xem `VERSION_NOTICES["3.5.0"].critical_notices` trong `vnbroker/config.py`.