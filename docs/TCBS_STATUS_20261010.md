# BẢN GHI TỔNG HỢP — TCBS · để làm tiếp Thứ Hai 2026-10-12

**Cập nhật:** 2026-10-10 (Thứ Bảy) · **HEAD:** `92ecb8b` + script probe (chưa commit lúc viết)
**Phạm vi:** 4 đợt TCBS · **Nguồn chi tiết:** `docs/REPORT_TCBS_ROUND4.md`

> **Câu đầu tiên phải đọc:** hôm nay **Thứ Bảy**, phái sinh VN nghỉ. Không có việc
> kiểm chứng nào làm được trước Thứ Hai. Đừng tạo lênh thật để "thử xem" — mọi
> thứ quan trọng đều nằm ở mục 4.

---

## 1. ĐÃ XONG — không cần làm lại

| # | Việc | Kết quả | Commit |
|:--|:--|:--|:--|
| 1 | TokenManager + 2 endpoint `gaia` | JWT decode cục bộ, cache, `token_provider` | `f056318` |
| 2 | 4 endpoint tiền/vay + pricing-policy | deposit/withdraw/transfer | `90ead64` |
| 3 | Condition cancel + securities | | `8e4f959` |
| 4 | Coverage 47/48 path spec | `/api/v1/derivatives/contracts` cố ý không nối | `f23786b` |
| 5 | Sửa lỗi 4xx bị trả như thành công | | `bc9d786` |
| 6 | Hệ thống lessons | 24 lesson / 5 file + cổng `check_lessons.py` | `5f7b83f` |
| 7 | Cổng chặn payload (`check_tcbs_bodies.py`) | 12 write method, self-test 10 case | `4654ff7` |
| 8 | Tách `derivatives.py` 852L → 462L | API không đổi (0 chữ ký khác biệt) | `61ab18b` |
| 9 | Race `_store_token` + lọc kwargs nhạy cảm | | `93a89e8` |
| 10 | Sửa 7 lỗi audit | | `ee0fbc5` |
| 11 | **Sửa 38 lệch payload theo spec** | **cổng: 0 lệch, baseline rỗng** | `ea55936` |
| 12 | TTL đo được: 8h → **24h** | + 9 chỗ trong `docs/` | `7aef6af` |
| 13 | 2 test DNSE ERROR → skip | `pytest-full` xanh lần đầu trong 4 đợt | `7aef6af` |
| 14 | Bằng chứng probe server thật | `docs/evidence/tcbs-probe-20261010.json` (**đã khử PII**) | `2599872` |

### 1.1 Ba thay đổi căn bản

- **Nợ payload = 0.**
- **Có JWT thật** (`.env`, RS256, hết hạn 19:10 hôm nay) ⇒ lần đầu **đo được**.
- **Bản đồ path thật**: 48 path spec · 47 nối · 1 cố ý bỏ.

### 1.2 Ba số đo được

| Đo | Giá trị |
|:--|:--|
| TTL JWT | **`exp - iat` = 86400s = 24.0 giờ** (tài liệu cũ ghi ~8h — sai) |
| `custodyID` | Lấy từ claim JWT (không hardcode) |
| `scopes` | `['bond','fund','stock','socket:all']` — **không kết luận được** (xem §3.2) |

## 2. TÒN ĐỌNG — theo mức ảnh hưởng

### 2.1 🔴 5 method phái sinh chưa từng được server xác nhận

Đã sửa đúng theo spec, **chưa có bằng chứng server chấp nhận**. Spec **không có**
endpoint validate/dry-run ⇒ muốn biết payload đúng không thì **chỉ có một cách:
gửi lệnh thật**.

| Method | Cần xác nhận |
|:--|:--|
| `place_derivative_order` | `volume` + `refId` thay cho `quantity`/`requestId` |
| `place_derivative_condition_order` | `soPrice`; `callbackPoint`+`activationPrice` chỉ khi TSO |
| `change_derivative_order` | `accountId`+`subAccountId`+`orderNo`+`nvol`+`nprice` |
| `change_derivative_condition_order` | `pkOrderNo`+`soPrice`; đã bỏ `quantity`/`price` |
| `cancel_derivative_order` | `accountId`+`orderNo` |

### 2.2 🟠 3 endpoint bị server từ chối

| Path | Lỗi |
|:--|:--|
| `/hydros/v1/account/{accountNo}/pricing-policy` | 403 `877006` |
| `/hydros/v1/account/{accountNo}/risk` | 403 `877006` |
| `/khaos/v1/loan/{accountNo}` | 400 `875001` (mọi định dạng accountNo) |

Hai endpoint hydros **từng được báo PASS ở Round 2 bằng mock**.

### 2.3 🟡 `/aion/v1/accounts/{accountNo}/orders/history`

Không 404, nhưng response **giống y hệt** `/orders/zzz-bia`, và `pageSize` bị echo
⇒ **wildcard bắt 1 segment cuối**. Không đủ bằng chứng để mở lại. Chỉ phân biệt
được khi tài khoản có lịch sử lệnh thật.

### 2.4 🟡 Nợ kỹ thuật

| Việc | Vị trí |
|:--|:--|
| Sát ngưỡng 800L | `quote.py` 793 (còn 7L) · `websocket.py` 791 (còn 9L) |
| `_post` trùng lặp | `equity.py`, `money.py` còn bản riêng (2 file đã qua `_write_http`) |
| `set_token()` nên là `Optional[int]` | vá điểm ghi race, chưa sửa hẹp |
| `check_and_update_state()` **0 caller** | `session.py:161` — bẫy đang ngủ |

## 3. BA ĐIỀU ĐÃ SỬA SAI — đừng lặp lại

### 3.1 Claim "thiếu derivative scope" — **chưa đủ căn cứ**

Tôi suy ra từ `scopes` trong JWT. Nhưng:
- **Cả 4** endpoint `/khronos/*` trả **cùng** `500/210000` *"không thể thực hiện vào
  lúc này"* ⇒ lỗi theo **thời gian**. Từ chối quyền sẽ trả **401/403**.
- `/tartarus/v1/derivatives` — market data phái sinh — trả **200 thật**.

⇒ `scopes` **không phải** danh sách đầy đủ capability. **Đừng xin quyền khi chưa đo.**

### 3.2 Chi tiết tôi bịa

Bản đầu báo cáo ghi *"probe lúc ~17:00, sau 15:00"*. **Tôi không ghi giờ probe.**
Nguyên nhân thật đơn giản: **Thứ Bảy**.

### 3.3 Năm kết luận sai khác

Xem `docs/REPORT_TCBS_ROUND4.md` §6. Cùng một nguyên nhân: **tin phản hồi 200 mà
không kiểm chứng nó đúng là của endpoint mình hỏi**.

## 4. KẾ HOẠCH THỨ HAI

### Bước 0 — Token (2 phút)
Token hết hạn **19:10 Thứ Bảy**. Thứ Hai nó **đã hết hạn** ⇒ phải lấy lại:
```powershell
pwsh -File "$env:TEMP\getjwt.ps1"   # nhập Smart OTP (iOTP) từ app TCInvest
```

### Bước 1 — Chạy probe chỉ-đọc (1 phút, không tạo lệnh)
```powershell
.venv\Scripts\python.exe scripts\probe_tcbs_khronos_readonly.py
```
Đọc kết quả theo đúng bảng này — **đừng suy diễn**:

| `account status` trả | Kết luận | Hành động |
|:--|:--|:--|
| **200** | Tài khoản **đủ quyền** | §3.1 của tôi là **suy đoán sai** → **xoá khỏi việc**, báo Owner |
| **500/210000** | Vẫn ngoài giờ (chạy sai giờ) | Chạy lại trong `09:00–11:30` hoặc `13:00–14:45` |
| **401/403** | **Thiếu quyền thật** | Báo Owner, **không sửa code** |

### Bước 2 — Nếu bước 1 ra 200
Gate đỏ duy nhất còn lại là **xác nhận payload write**. Nhưng:
- Chưa được giao quyền **đặt lệnh thật** trên tài khoản Owner.
- Cần Owner **đồng ý rõ ràng** trước khi gọi bất kỳ `/khronos/v1/order/*` nào.

⇒ Việc mặc định an toàn: **báo cáo kết quả, dừng lại.**

### Bước 3 — Việc không cần giờ giao dịch (làm được ngay Thứ Hai)
- §2.4 — dọn nợ kỹ thuật.
- §2.3 — hỏi Owner có muốn mở lại `orders/history` không.

### Bước 4 — Gate trước khi kết thúc
```powershell
pwsh -NoProfile -File scripts/check_all.ps1      # phải 8/8, exit 0
```

## 5. AN TOÀN — ràng buộc đã cài

| Cơ chế | Chặn cái gì |
|:--|:--|
| `check_tcbs_bodies.py` | payload lệch spec (0 lệch) |
| `write_gate` + `session.enable_write()` | lệnh ghi khi chưa mở quyền |
| `probe_tcbs_khronos_readonly.py` | **chỉ GET**; `WRITE_GUARD` + `READ_ALLOWLIST` — **đã kiểm chứng**: chèn `/khronos/v1/order/place` vào danh sách ⇒ `AssertionError` |
| `dry_run=True` mặc định ở mọi write method | gọi nhầm không gửi HTTP |

> ⚠ **Probe chỉ-đọc được bảo vệ ở tầng `assert`, không phải ở tầng network.** Sửa
> `PROBES` là có thể vượt. Đừng sửa nó mà không đọc lại `WRITE_GUARD`.

## 6. Một sự cố chưa giải thích

Một lần gate báo `FAIL: 1 self-test gate that FAIL` ngay sau khi ghi docs.
**Không tái hiện được** ở 3 lần chạy đầy đủ liên tiếp sau đó (9/9 + 10/10, PASS).
Không có bằng chứng để gán nguyên nhân. Nếu thấy lại: **chạy lại 3 lần trước khi
kết luận**, rồi ghi vào báo cáo.

## 7. Kinh nghiệm 4 đợt — đọc trước khi kế hoạch

1. **Nạp `docs/LESSONS/` (24 bài) trước khi lập kế hoạch.**
2. **Cổng mới luôn cần audit độc lập.** L-G05/06/07 là lỗi **của cổng tôi viết trong
   cùng phiên**, chỉ lộ khi refactor và đọc lại con số.
3. **Đừng tin phản hồi 200 nếu chưa kiểm chứng nó đúng là của endpoint mình hỏi.**
4. **Test xanh ở cả hai trạng thái = bằng chứng bằng 0** → gỡ, đừng giữ làm vỏ.
5. **Vượt ngân sách dòng thì tách cấu trúc, không xoá comment.**
6. **Không báo PASS cho thứ chưa chạy.** DNSE: đã `git stash` rồi chạy HEAD sạch để
   chứng minh là lỗi môi trường — bằng chứng đó đáng giá hơn "chắc là do mạng".