# BÀN GIAO — Session sau · TCBS Round 5

**Gửi session:** 2026-10-10 · **Từ:** Round 4 (sửa 38 lệch payload + lần đầu đo được trên server thật)
**Trạng thái:** đã push `origin/dev @ 7aef6af` · **8/8 gate PASS**.

> **Câu đầu tiên phải đọc:** 3 điều đã thay đổi căn bản so với 4 đợt trước —
> nợ payload đã **zero**, và ta **đã có JWT thật**. Việc tiếp theo không còn là
> "đoán", mà là **kiểm chứng thứ đã sửa**.

---

## 1. Còn nợ — theo thứ tự ưu tiên

### 1.1 🔴 Xin derivative scope — chặn lớn nhất
`scopes = ['bond','fund','stock','socket:all']` — **không có derivative**.
Hệ quả: 5 method `/khronos/*` đã sửa đúng theo spec nhưng **chưa từng được
server xác nhận**. Đây là phần lớn giá trị SDK phái sinh.

Cần Owner mở quyền cho tài khoản. Sau đó, trong **giờ giao dịch**:

```
POST /khronos/v1/order/place   → xem có 422/400 vì payload không?
POST /khronos/v1/order/cancel  → xác nhận `accountId`+`orderNo` đúng
```

⚠ **Đặt lệnh thật là việc chưa được giao.** Cần Owner đồng ý rõ ràng trước.

### 1.2 🔴 Token hết hạn **19:10 hôm nay**
```powershell
pwsh -File "$env:TEMP\getjwt.ps1"   # nhập Smart OTP (iOTP) từ app TCInvest
```
Token đo được sống **24 giờ** (`exp - iat = 86400s`), không phải 8.

> Sau mốc này, **mọi kết luận server trong `docs/REPORT_TCBS_ROUND4.md` hết hiệu
> lực**. Không dùng lại mà không probe lại.

### 1.3 🟠 3 endpoint bị server từ chối

| Path | Lỗi |
|:--|:--|
| `/hydros/v1/account/{accountNo}/pricing-policy` | 403 `877006` |
| `/hydros/v1/account/{accountNo}/risk` | 403 `877006` |
| `/khaos/v1/loan/{accountNo}` | 400 `875001` Forbidden (mọi định dạng accountNo) |

Hai endpoint hydros **từng được báo PASS ở Round 2 bằng mock**. Hoặc Owner xin
quyền, hoặc chấp nhận chúng luôn lỗi với tài khoản này.

### 1.4 🟠 `/aion/v1/accounts/{accountNo}/orders/history`
Không 404, nhưng response **giống y hệt** một path bịa (`/orders/zzz-bia`), và
`pageSize` bị echo ⇒ **wildcard bắt 1 segment cuối**. **Không đủ bằng chứng để mở
lại.** Chỉ phân biệt được khi tài khoản có lịch sử lệnh thật.

### 1.5 🟡 `/api/v1/derivatives/contracts`
**404 cả GET lẫn POST** ⇒ không tồn tại trên production. **Không nối.**
Coverage giữ 47/48, giờ có bằng chứng server.

### 1.6 🟡 Nợ kỹ thuật

| # | Việc | Vị trí |
|:--|:--|:--|
| — | `quote.py` 793L (còn 7L) · `websocket.py` 791L (còn 9L) | sát ngưỡng 800 |
| — | `_post` trùng lặp: `equity.py`, `money.py` còn bản riêng | `derivative_orders` + `equity_orders` đã qua `_write_http` |
| — | `session.set_token()` nên là `Optional[int]` | vá điểm ghi race, chưa sửa hẹp |
| — | `check_and_update_state()` **0 caller** | `session.py:161`, bẫy đang ngủ |

## 2. Bản đồ sau Round 4

```
vnbroker/broker/tcbs/
  token_manager.py       303L  JWT decode cục bộ, cache, token_provider
  _write_http.py         155L  POST + map 400/404/422/429 + describe_business_code
  derivative_orders.py   354L  DerivativeWriteMixin · 10 method write phái sinh
  equity_orders.py       242L  EquityWriteMixin · 3 method write cổ phiếu  (MỚI)
  _equity_common.py       66L  _PATHS + _validate_order_input dùng chung   (MỚI)
  condition_orders.py    187L  huỷ lệnh điều kiện
  derivatives.py         462L  (đã tách từ 852L) · chỉ còn method đọc
  auth.py                306L  +apikey/info, +apikey/extend, hạn từ claim exp
  money.py               773L  +pricing-policy, +deposit/withdraw/transfer
  equity.py              546L  ⚠ đã tách (808L)
  client.py              822L  facade
docs/
  LESSONS/                       24 lesson / 5 file
  tcbs_body_baseline.json        **0 dòng** — nợ đã trả hết
  evidence/tcbs-probe-20261010.json   bằng chứng probe (đã khử PII)
  REPORT_TCBS_ROUND4.md          báo cáo đợt này
```

## 3. Gate dùng lại

```powershell
pwsh -NoProfile -File scripts/check_all.ps1          # đầy đủ ~6 phút
pwsh -NoProfile -File scripts/check_all.ps1 -Quick   # bỏ pytest toàn bộ
```
> ⚠ `-Quick` **không phải** bằng chứng merge — nó bỏ `pytest-full`.

```powershell
.venv\Scripts\python.exe scripts\check_tcbs_bodies.py --report
.venv\Scripts\python.exe scripts\check_tcbs_bodies.py --self-test
.venv\Scripts\python.exe scripts\check_lessons.py
.venv\Scripts\python.exe scripts\verify_tcbs_coverage.py
```

> ⚠ `test_news_integration.py` gọi mạng thật `kbbuddywts.kbsec.com.vn` và
> **flaky**. Đã gặp 4 lần trong 3 đợt. **Chạy lại lần hai trước khi báo đỏ.**

## 4. Bài học mang sang — đọc TRƯỚC khi kế hoạch

`docs/LESSONS/` — 24 bài. Ba bài sinh ra từ chính lỗi của Round 4:

| Mã | Tóm tắt |
|:--|:--|
| **L-G05** | Cổng bỏ sót `payload["x"] = …` (field ghi sau dict literal) |
| **L-G06** | Cổng dùng map **toàn cục theo tên key** ⇒ file sort trước chiếm mất key, quét nhầm sang path khác |
| **L-G07** | `subprocess(text=True)` không khai `encoding` ⇒ decode lỗi ⇒ `stdout=None` ⇒ gate **báo xanh khi nhiệm vụ thất bại** |

Ngoài ra `L-E01` (số trong tài liệu ≠ số đo) — đã ăn vào ngay: TTL 8h→24h,
18 path "đã chết" → 17 chết, 3 endpoint "hỏng" → lỗi probe của tôi.

## 5. Quy trình — rút ra từ 4 đợt

1. **Nạp `docs/LESSONS/` trước khi lập kế hoạch.**
2. **Cổng mới luôn cần audit độc lập.** L-G05/06/07 là lỗi **của cổng tôi viết
   trong cùng phiên**, chỉ lộ khi refactor và đọc lại con số.
3. **Đừng tin phản hồi 200 nếu chưa kiểm chứng nó đúng là của endpoint mình hỏi.**
   4/5 kết luận sai của tôi đều từ đây.
4. **Test xanh ở cả hai trạng thái = bằng chứng bằng 0** → gỡ, đừng giữ làm vỏ.
5. **Vượt ngân sách dòng thì tách cấu trúc, không xoá comment.**

## 6. Việc admin

- Branch cũ (`feat/a1-bars`, `feat/a2-ws`, `feat/a3-legacy`, `docs/plan-tcbs`)
  đã merge, có thể xoá.
- **CI GitHub Actions không chạy** (billing). Mọi gate chạy local qua `check_all.ps1`.