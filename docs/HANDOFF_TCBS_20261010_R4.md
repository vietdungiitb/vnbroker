# BÀN GIAO — Session sau · TCBS Round 4

**Gửi session:** 2026-10-10 · **Từ:** Round 3 (cổng chặn payload + dọn nợ kỹ thuật)
**Trạng thái:** đã merge `dev`, **đã push `origin/dev @ c917399`**, gate xanh.

> **Câu đầu tiên phải đọc:** Round 3 **không sửa lỗi**, nó **dựng cổng chặn** và báo cáo.
> Việc sửa cần Owner chốt + JWT. Nút thắt vẫn là **chưa có Smart OTP từ app TCInvest**.

---

## 1. Việc còn nợ — theo thứ tự

### 1.1 🔴 **Lấy JWT** — chặn mọi xác minh còn lại
```powershell
pwsh -File "$env:TEMP\getjwt.ps1"
```
Cần **Smart OTP (iOTP) từ app TCInvest**. Việc của Owner — không giải quyết bằng code.

| # | Ngay khi có JWT | Vì sao |
|:--|:--|:--|
| 1 | **Đo tập `rc` thật** của 12 write endpoint | Quyết định có raise theo `rc` hay không (R2) |
| 2 | **Kiểm chứng 38 lệch payload** | Sửa mà không đo là **đoán** |
| 3 | **Đo TTL thật của JWT** | Nếu TCBS **không** phát `exp` thì session không tự hết hạn |
| 4 | **Đo lại `countBack`/resolution phút** | Đang là hệ số ước lượng `_TRADING_DAY_RATIO = 0.70` |
| 5 | **Probe 18 path đợt 1 đã gỡ** | Nếu còn sống ⇒ `git revert` commit gỡ |

### 1.2 🔴 38 lệch payload — **cần Owner chốt**
Chi tiết đầy đủ: `docs/REPORT_TCBS_ROUND3.md` §0.
Bản đầy đủ: `.venv\Scripts\python.exe scripts\check_tcbs_bodies.py --report`

Ba câu hỏi cần trả lời:
1. Sửa thẳng theo spec (đổi chữ ký `request_id` → `refId`) hay giữ tương thích rồi map?
2. `_gated_change_derivative_order` thiếu **6 field bắt buộc** — lệnh sửa lệnh phái sinh
   hiện gần như chắc chắn bị TCBS từ chối. Có lịch sử gọi thật chưa?
3. `pinCode` trong `_gated_place_order` là gì? Spec `/akhlys/.../orders` không có nó.

### 1.3 🟠 `/api/v1/derivatives/contracts` — REST hay WebSocket?
Spec tự mâu thuẫn: path `/api/v1/…` REST, `summary` = *"Price board (WSS, derivative)"*,
`description` = *"over WebSocket"*, response **không có `content`**. Là path cuối
chưa nối của 48 path spec.

### 1.4 🟡 Nợ kỹ thuật

| # | Việc | Vị trí | Ghi chú |
|:--|:--|:--|:--|
| N4 | File sát ngưỡng 800L | `equity.py` 798 (2L) · `quote.py` 793 (7L) · `websocket.py` 791 (9L) | Thêm 1 method là vượt im lặng |
| N8 | `_post` trùng lặp | `equity.py:657`, `money.py:702` | `derivative_orders.py` đã chuyển sang `_write_http.post_json` |
| N7 | `requestId` hư cấu còn lại | `equity.py:394,454,525` | `derivatives` đã nằm trong baseline của cổng |
| — | `session.set_token(expires_in_seconds)` nên là `Optional[int]` | `session.py:76` | Đợt này vá điểm ghi race, không sửa hẹp |
| — | `check_and_update_state()` **0 caller** | `session.py:161` | Bẫy đang ngủ — test canh báo trong `test_tcbs_round3_fixes.py` |

## 2. Bản đồ sau Round 3

```
vnbroker/broker/tcbs/
  token_manager.py       303L  JWT decode cục bộ, cache, token_provider, on_expiring
  _write_http.py         155L  POST + map 400/404/422/429 + describe_business_code
  derivative_orders.py   354L  MỚI · DerivativeWriteMixin (10 method write phái sinh)
  condition_orders.py    187L  huỷ lệnh điều kiện
  derivatives.py         462L  (đã tách từ 852L) · chỉ còn method đọc
  auth.py                306L  +apikey/info, +apikey/extend, hạn từ claim exp
  money.py               773L  +pricing-policy, +deposit/withdraw/transfer
  equity.py              798L  ⚠ chỉ còn 2L dưới ngân sách
  client.py              772L  facade
docs/
  LESSONS/                      24 lesson / 5 file — đọc TRƯỚC khi sửa
  tcbs_body_baseline.json       38 lỗi payload đã biết
scripts/
  check_lessons.py              C1/C2/DRIFT + self-test 9 case
  check_tcbs_bodies.py          payload vs spec + self-test 10 case
  verify_tcbs_coverage.py       48 path · 47 nối · 1 chưa
```

## 3. Gate dùng lại

```powershell
pwsh -NoProfile -File scripts/check_all.ps1        # đầy đủ, ~5 phút
pwsh -NoProfile -File scripts/check_all.ps1 -Quick # bỏ pytest toàn bộ
```
> ⚠ **`-Quick` KHÔNG phải bằng chứng merge** — nó bỏ `pytest-full`. Trước khi merge
> phải chạy không `-Quick`.

```powershell
.venv\Scripts\python.exe scripts\check_tcbs_bodies.py --report      # xem 38 lệch
.venv\Scripts\python.exe scripts\check_tcbs_bodies.py --write-baseline docs\tcbs_body_baseline.json
.venv\Scripts\python.exe scripts\verify_tcbs_coverage.py
.venv\Scripts\python.exe scripts\check_lessons.py
```

> ⚠ `test_news_integration.py` gọi mạng thật `kbbuddywts.kbsec.com.vn` và **flaky**.
> Đây là lần thứ 4 trong 3 đợt mà một lần chạy đơn lẻ dẫn tới kết luận sai.
> **Chạy lại lần hai trước khi báo đỏ.**

## 4. Quy trình — kinh nghiệm từ Round 3

1. **Nạp `docs/LESSONS/` TRƯỚC khi lập kế hoạch.** 24 bài học, mỗi cái có `CHECKLIST`.
2. **Cổng mới luôn cần audit độc lập.** Cả 4 lỗi trong `gate-integrity.md` là lỗi
   của cổng **do tôi viết trong cùng phiên** — chỉ audit mới thấy.
3. **Test xanh ở cả hai trạng thái = bằng chứng bằng 0.** Đã gỡ 2 test vì lý do này.
4. **Đừng sửa lỗi tiền thật khi không có cách kiểm chứng.** Dựng cổng + báo cáo Owner,
   đừng đoán rồi "sửa cho có".

## 5. Việc admin

- Branch `feat/a1-bars` · `feat/a2-ws` · `feat/a3-legacy` (đợt 1) + `docs/plan-tcbs`
  còn local/remote — đã merge, có thể xoá.
- **CI GitHub Actions không chạy** (billing). Mọi gate chạy local qua `check_all.ps1`.