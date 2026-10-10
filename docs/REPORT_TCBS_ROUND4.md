# BÁO CÁO — TCBS Round 4: sửa 38 lệch payload + lần đầu có bằng chứng server thật

**Ngày:** 2026-10-10 · **Trạng thái:** đã push `origin/dev @ 7aef6af`
**Kế thừa:** `docs/HANDOFF_TCBS_20261010_R4.md` · Lessons áp dụng: L-E01, L-G05, L-G06, L-G07

> **Ba điều đã đổi trong đợt này, không đợt nào trước có:**
> 1. **38 lệch payload → 0.** Không còn nợ.
> 2. **Có JWT thật** ⇒ lần đầu đo được số thay vì đoán.
> 3. **38 phát hiện trong đó 5 là lỗi của chính tôi** — đã ghi đủ ở §6.

---

## 1. Quyết định của Owner và kết quả

Owner trả lời 4 câu hỏi ở Round 3:

| # | Câu hỏi | Owner chốt |
|:--|:--|:--|
| 1 | 38 lệch payload | **Sửa thẳng theo spec** (kiểm chứng sau) |
| 2 | `/api/v1/derivatives/contracts` | *"theo bạn làm thế nào tốt"* |
| 3 | `pinCode` | *"spec không có thì loại bỏ"* |
| 4 | JWT lấy thế nào | *(hỏi lại)* |

### §1.1 Kết quả: `lech moi: 0`, baseline **rỗng**

| Nhóm | Trước | Sau |
|:--|:--|:--|
| Cổng `check_tcbs_bodies` | 12 payload · **38 lệch** | 12 payload · **0 lệch** |
| `docs/tcbs_body_baseline.json` | 38 dòng nợ | **0 dòng** |

### §1.2 Sửa gì (wire payload = đúng spec)

| Endpoint | Sửa |
|:--|:--|
| `/akhlys/.../orders` | **BỎ** `pinCode` + `requestId` — spec chỉ có 5 field |
| `/akhlys/.../orders/{orderId}` | **BỎ** `requestId` |
| `/akhlys/.../cancel-orders` | **BỎ** `requestId` |
| `/khronos/v1/order/place` | `quantity`→`volume`, `requestId`→`refId` |
| `/khronos/v1/order/condition/place` | `quantity`→`volume`, `triggerPrice`→`soPrice`, `requestId`→`refId`, **thêm** `callbackPoint`/`activationPrice` (chỉ khi TSO) |
| `/khronos/v1/order/change` | **THÊM** `accountId`+`subAccountId`, `orderId`→`orderNo`, `quantity`→`nvol`, `price`→`nprice`, `requestId`→`refId` |
| `/khronos/v2/order/condition/change` | `orderId`→`pkOrderNo`, `triggerPrice`→`soPrice`, `requestId`→`refId`, **BỎ** `quantity`+`price` |
| `/khronos/v1/order/cancel` | **THÊM** `accountId`, `orderId`→`orderNo`, `requestId`→`refId` |

### §1.3 ĐỔI CHỮ KÝ — phá vỡ có chủ đích

| Method | Thay đổi |
|:--|:--|
| `change_derivative_order` | **+** `account_id`, `sub_account_id` |
| `change_derivative_condition_order` | **−** `quantity`, `price` · **+** `account_id` |
| `cancel_derivative_order` | **+** `account_id` |
| `client.modify_order` / `client.cancel_order` | `pin_code` → `request_id` |

Gọi bằng chữ ký cũ **ném `TypeError`** — cố ý. Sai payload âm thầm nguy hiểm hơn lỗi nổi.

### §1.4 Mâu thuẫn nội bộ của spec — chỗ tôi **không** sửa theo mù

`/khronos/v1/order/condition/place` để `callbackPoint` + `activationPrice` trong
`required`, nhưng `description` lại ghi *"only for orderType = TSO"*.

⇒ Chọn theo **mô tả**: chỉ gửi khi `order_type == "TSO"`; thiếu thì raise
`MISSING_TRAILING_PARAMS`. Gửi `0` cho lệnh SOL/SOU có thể khiến TCBS từ chối
cả đơn. **Đây là chỗ duy nhất tôi không làm theo `required` — và có lý do.**

## 2. §2 — JWT: **đã có sẵn, không cần lấy**

Hỏi "JWT lấy thế nào" thì phát hiện `.env` **đã có** `TCBS_JWT_TOKEN` (1290 ký tự,
RS256). Trước 4 đợt đều ghi "chưa có JWT" — **đó là sai, chỉ là chưa ai mở `.env` kiểm.**

```powershell
pwsh -File "$env:TEMP\getjwt.ps1"   # chỉ cần khi hết hạn: nhập Smart OTP (iOTP)
```

### §2.1 Ba số đo được — hai số trong tài liệu sai

| Đo được | Tài liệu ghi | Hậu quả nếu giữ nguyên |
|:--|:--|:--|
| **TTL = 86400s = 24.0 giờ** (`exp - iat`) | ~8 giờ | token còn hiệu lực bị coi là **đã chết** sớm 16 giờ |
| `custodyID = 105C836591` trong claim | phải đoán | không gọi được `/aion/v1/customers/{custodyId}/accounts` |
| `scopes = ['bond','fund','stock','socket:all']` | chưa biết | **không có derivative** ⇒ `/khronos/*` không kiểm chứng được |

Đã sửa `session.py` + **9 chỗ** trong `docs/`. **Không đụng DNSE** — broker khác,
chưa đo thì để nguyên.

### §2.2 Tách 2 khái niệm bị gộp nhầm ở `session.py`

`SESSION_TIMEOUT_SECONDS = 28800` (**timeout nhàn rỗi**) và hạn token từng được
đọc là một. Comment `8 hours default` nằm ngay trên hằng số nhàn rỗi ⇒ ai đọc cũng
nghĩ hạn token là 8 giờ. Giờ tách rõ + thêm `TCBS_JWT_TTL_SECONDS = 86400`.

## 3. §3 — Probe server thật: lần đầu trong 4 đợt

**Chỉ GET.** Không gọi verb ghi lệnh. Bằng chứng đã khử PII ở
`docs/evidence/tcbs-probe-20261010.json` (tên, số tài khoản, số ngân hàng).

Quét **33 endpoint GET** trong spec: **14 trả 200 thật**.

### §3.1 Trả lời câu hỏi #2 của Owner: `/api/v1/derivatives/contracts`

**404 ở CẢ GET lẫn POST.** Path không tồn tại trên production.

⇒ **Không nối.** Coverage giữ **47/48** — giờ có bằng chứng server thay vì suy luận
từ mâu thuẫn nội bộ của spec.

### §3.2 18 path đã gỡ ở Round 1

| Kết quả | Số |
|:--|:--|
| 404 thật ⇒ **quyết định gỡ đúng** | **17** |
| Không 404 nhưng response **giống y hệt** một path bịa | **1** |

`/aion/v1/accounts/{accountNo}/orders/history` trả 200 — nhưng
`/orders/zzz-bia` và `/orders/zzz-khong-ton-tai` trả **y hệt từng byte**
(`{"object":"list","pageSize":7,"pageIndex":1,"totalCount":0,"data":null}`), và
`pageSize` bị echo lại ⇒ **wildcard bắt 1 segment cuối**, không phân biệt được
route thật với route bịa.

⇒ **KHÔNG khôi phục.** Không đủ bằng chứng. Cần đặt lệnh thật rồi đọc lịch sử
(ngoài phạm vi an toàn) hoặc hỏi Owner.

### §3.3 Endpoint bị server từ chối

| Path | Kết quả |
|:--|:--|
| `/hydros/v1/account/{accountNo}/pricing-policy` | **403** `877006` "Yêu cầu bị từ chối" |
| `/hydros/v1/account/{accountNo}/risk` | **403** `877006` |
| `/khaos/v1/loan/{accountNo}` | **400** `875001` Forbidden (cả 3 định dạng accountNo) |

2 endpoint hydros **từng được báo "PASS" ở Round 2** bằng mock. Server thật từ chối.
⇒ **Rủi ro còn lại R1 ở §5.**

### §3.4 `/khronos/*` trả 500 — nhưng KHÔNG phải endpoint hỏng

```
500  210000  "Yêu cầu không thể thực hiện vào lúc này, vui lòng quay lại sau"
```

Đó là **ngoài giờ giao dịch** (probe lúc ~17:00, sau 15:00), không phải lỗi.

## 4. §4 — 3 lỗ hổng của CỔNG do chính tôi tạo ra trong lúc sửa

Cả 3 đều làm cổng **báo sai**, và cả 3 đều lộ ra **vì tôi refactor**, không phải vì ai audit.

| Mức | Lỗ hổng | Hậu quả | Bằng chứng |
|:--|:--|:--|:--|
| **L-G05** | Quét chỉ đọc dict literal, **bỏ sót** `payload["x"] = …` | Báo `MISSING` cho field **có** gửi ⇒ dễ khiến người sau ghi 2 dòng này vào baseline cho xanh | Thêm `payload["zzzBogusSubscript"]=1` → `EXTRA`, exit 1 ✓ |
| **L-G06** | `package_index` khóa theo **TÊN key**, `setdefault` ⇒ file sort trước thắng | File mới `_equity_common.py` (`_` < `d`) chiếm key `place_order` ⇒ **5 method derivative quét nhầm sang path cổ phiếu, báo 9 lệch SAI** | Sửa phân giải theo module ⇒ 12 payload, 0 lệch ✓ |
| **L-G07** | `check_mypy_baseline.py` dùng `text=True` **không khai `encoding`** | Decode cp1252 → `UnicodeDecodeError` trong thread reader ⇒ `stdout=None` ⇒ `(proc.stdout or "")` nuốt thành **chuỗi rỗng** ⇒ **gate XANH khi mypy thất bại** | Sửa `encoding="utf-8", errors="replace"` ✓ |

**L-G07 nguy hiểm nhất**: gate báo xanh trong khi nhiệm vụ của nó là bắt lỗi.
Cùng nhóm với `check_lessons.py` — đã có `encoding` ở 3/4 chỗ, chỗ thứ 4 sót.

**Tôi không ghi 2 lỗi đầu vào baseline** — chúng là lỗi của cổng, không phải nợ payload.

## 5. §5 — 2 bug có sẵn phát hiện khi refactor

`client.modify_order()` và `client.cancel_order()` truyền `pin_code=` cho method
**không có tham số đó** ⇒ **`TypeError` mỗi lần gọi**.

Đã có từ trước; mypy chỉ bắt được khi phân giải lại qua mixin. Đã sửa và
**chứng minh bằng cách gọi thật** với mock (không chỉ đọc code).

### §5.1 Hồi quy do chính tôi: vượt 800L

Sửa payload làm `equity.py` **808 dòng** ⇒ vỡ test ngân sách dòng.

**Không nén bằng cách xoá comment** — cấu trúc sai thì lần sửa sau lại vượt tiếp.
Tách `equity_orders.py` (`EquityWriteMixin`, 242d) + `_equity_common.py` (66d) để
**tránh import vòng** (`equity_orders` cần `_PATHS` của `equity`, mà `equity` lại
cần mixin). `equity.py`: **808 → 546 dòng**.

> Bài học cũng đã phải trả phí: `split.py` viết khối 2 lần và `split3.py` dedent
> ra **ngoài class**, làm `place_order` biến mất khỏi service mà cổng vẫn báo xanh
> (9/12 payload thay vì 12/12). Chỉ lộ khi **đọc lại con số 12**.

## 6. §6 — 5 kết luận sai của chính tôi, đính chính tại chỗ

Đây là phần tôi cho là quan trọng nhất của đợt này.

| Tôi khẳng định | Thực tế |
|:--|:--|
| "3 endpoint `/nyx/v1/intraday/*` cần sửa" | **Probe của tôi truyền chuỗi literal `{ticker}`** → 200 nhãm. Vòng 2 truyền `TCB` thật → 200 kèm data thật |
| "`/eros/.../get-profile` lỗi `Cannot change Accept-Language`" | Lỗi **do probe của tôi** gửi header học. Bỏ header → 403 (route sống, bị từ chối quyền) |
| "18 path đã gỡ đều đã chết" | **17** chết. 1 path không 404 nhưng không phân biệt được với wildcard |
| "`/khaos/v1/loan` sai định dạng accountNo" | Sai cả 3 định dạng ⇒ **quyền**, không phải định dạng |
| "Chưa có JWT, cần Smart OTP từ Owner" | `.env` **đã có** token còn hiệu lực |

Bốn trong năm là lỗi **đo sai**, không phải lỗi suy luận. Nguyên nhân chung: **tin
kết quả 200 mà không kiểm chứng phản hồi có đúng là của endpoint mình hỏi**.

## 7. §7 — 2 test DNSE: ERROR → skip

Fixture `account_no` gọi `get_accounts()` **không bọc lớp bảo vệ**. Lỗi mạng tại
fixture sinh ra **ERROR**, không phải FAILED ⇒ `_skip_if_transport_failure` trong
thân test **không bao giờ chạy tới**.

⇒ `pytest-full` đỏ vì mạng DNSE, dù code không liên quan.
Đã bọc; nay **5/5** chỗ gọi mạng đều có guard. Ranh giới giữ nguyên: **chỉ lỗi
vận chuyển** mới skip, HTTP 400/403/404 vẫn phải fail.

**Bằng chứng đây là lỗi môi trường, không phải hồi quy của tôi**: `git stash` toàn
bộ thay đổi, chạy lại trên HEAD sạch → **vẫn đúng 2 error đó**.

## 8. §8 — Gate

| Gate | Round 3 | Round 4 |
|:--|:--|:--|
| ruff | 0 | **0** |
| mypy | 1266 → 1148 | 1266 → **1138** (fix 128) |
| contract | 72 | **72** |
| **tcbs-bodies** | 12 payload · **38 lệch** | 12 payload · **0 lệch** |
| lessons | 24/40 | **24/40** |
| self-test | 9/9 + 10/10 | **9/9 + 10/10** |
| **pytest-full** | 1918 passed / **2 ERROR** | **1919 passed / 30 skipped / 0 ERROR** |
| | 7/8 gate | **8/8 gate** |

`pytest-full` xanh **lần đầu trong 4 đợt** — trước đó chỉ "gần xanh" vì DNSE.

## 9. §9 — ⚠ CHƯA CHẠY

| Việc | Vì sao |
|:--|:--|
| **Probe write endpoint** (đặt/hủy lệnh thật) | **Không làm** — tạo lệnh thật trên tài khoản Owner là việc chưa được giao |
| **Xác nhận `/khronos/*` nhận payload mới** | Tài khoản **không có derivative scope** + ngoài giờ giao dịch |
| **Đo tập `rc` thật** | Cần gọi write endpoint |
| Xác nhận `/aion/.../orders/history` là route thật | Cần có lịch sử lệnh thật |
| `hydros/*`, `khaos/loan` | Server từ chối quyền — cần Owner xin quyền |
| CI GitHub Actions | Job bị từ chối do billing |

## 10. §10 — Rủi ro còn lại

| # | Rủi ro | Mức |
|:--|:--|:--|
| **R1** | 5 endpoint `/khronos/*` **đã sửa đúng theo spec nhưng chưa từng được server xác nhận** — tài khoản không có derivative scope | **cao** |
| **R2** | `hydros/*` (2) + `khaos/loan` (1) bị server **từ chối** nhưng từng báo PASS bằng mock | **cao** |
| **R3** | `callbackPoint`/`activationPrice` — ta làm theo **mô tả**, spec ghi **required**. Nếu server bắt buộc cả hai → vẫn thiếu | trung bình |
| **R4** | Token hết hạn **19:10 hôm nay** ⇒ mọi kết luận server trong báo cáo này hết hiệu lực sau mốc đó | trung bình |
| **R5** | `quote.py` 793L / `websocket.py` 791L — chỉ còn 7–9L | thấp |

## 11. §11 — Việc còn lại cho Owner

1. **Xin derivative scope** cho tài khoản — không có thì 5 method phái sinh
   (chiếm phần lớn giá trị của SDK) không kiểm chứng được.
2. **Cấp quyền** `hydros/*` và `khaos/loan`, hoặc chấp nhận 3 endpoint này
   luôn trả lỗi với tài khoản này.
3. Xác nhận `/aion/v1/accounts/{accountNo}/orders/history` — có nên mở lại?
4. Token: làm mới trước **19:10** khi cần probe tiếp.