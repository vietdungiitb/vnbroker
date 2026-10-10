# BÀN GIAO — Session sau · TCBS Round 3

**Gửi session:** 2026-10-10 · **Từ:** Round 2 (TokenManager + 9 endpoint)
**Trạng thái khi bàn giao:** đã merge `dev`, **đã push `origin/dev @ 68ab1ce`**, gate xanh.

> **Câu đầu tiên phải đọc:** Round 2 đã đưa phủ API từ **39/48 lên 47/48** path.
> Còn **1** path, và nó **không phải vì thiếu code** — mà vì spec tự mâu thuẫn.
> **Nút thắt lớn nhất không phải code: chưa có JWT.** Mọi xác minh runtime còn lại
> đều bị chặn bởi việc lấy Smart OTP từ app TCInvest.

---

## 1. Còn nợ — thứ tự đề xuất

### 1.1 🔴 **Lấy JWT** — chặn mọi xác minh còn lại
```powershell
pwsh -File "$env:TEMP\getjwt.ps1"
```
- `.env` hiện chỉ có `TCBS_AUTH_TOKEN` = 48 ký tự tiền tố `10000928…` ⇒ đó là **API key**,
  **không phải JWT** (JWT phải có 3 phần).
- `apikey/info` → 200 (key hạn 2027-05-19). `oauth2/token` với OTP giả → 400 `203033 Invalid OTP`
  ⇒ **key được chấp nhận**, chỉ thiếu OTP thật.
- Cần **Smart OTP (iOTP) từ app TCInvest**. Đây là việc của Owner, **không** giải quyết
  được bằng code.

**Ngay khi có JWT, làm theo thứ tự này** — đo trước, sửa sau:

| # | Việc | Vì sao quan trọng |
|---|---|---|
| 1 | **Đo TTL thật của token** | Đợt này chỉ đọc claim `exp`. Nếu TCBS **không** phát `exp` thì session không tự hết hạn (rủi ro R2) |
| 2 | **Đo tập mã `rc` thật của write endpoint** | Quyết định có raise tự động hay không (rủi ro R1 — xem §2) |
| 3 | **Đo lại `countBack` / resolution phút** | Đang dùng `_TRADING_DAY_RATIO = 0.70` — **hệ số ước lượng** |
| 4 | **Probe 18 path đã gỡ ở đợt 1** | Nếu **vẫn sống** ⇒ `git revert` commit gỡ là đủ |
| 5 | **Kiểm chứng 9 endpoint mới** | Đúng theo spec nhưng **chưa gọi server lần nào** |

### 1.2 🟠 `/api/v1/derivatives/contracts` — cần Owner chốt
Đây là path duy nhất còn chưa nối, **và không nên nối mù**:

| Bằng chứng trong spec | Giá trị |
|---|---|
| path | `/api/v1/derivatives/contracts` (hình dạng REST) |
| `summary` | `Price board (WSS, derivative) (contracts)` |
| `description` | `Real-time derivative price board over WebSocket.` |
| `responses.200` | **không có `content`** — không mô tả body |

⇒ Spec **tự mâu thuẫn**: path REST nhưng mô tả WebSocket, và không định nghĩa được body.
**Câu hỏi cho Owner: đây là REST hay WebSocket?** Nếu REST cần TCBS bổ sung schema
response; nếu WebSocket thì phải xử lý ở tầng `explorer/tcbs/websocket.py`.

### 1.3 🟠 Rủi ro R1 — `HTTP 200 ≠ thành công` (việc tiền thật)
TCBS trả **HTTP 200 kèm mã nghiệp vụ** trong body (`rc` = `"1"` thành công, `<0` lỗi).
Thư viện **cố ý không raise theo `rc`**, vì spec chỉ ghi *"1: success, < 0: error"* — không
liệt kê đủ tập mã để suy ra "thành công", và chưa có JWT để đo thật. Raise theo tập đoán
có thể **chặn nhầm một lệnh hợp lệ**.

**Trong lúc chờ:** mọi caller phải tự kiểm.
```python
from vnbroker.broker.tcbs._write_http import describe_business_code

res = client.deposit_margin(..., dry_run=False)
if describe_business_code(res) != "1":
    ...  # lệnh bị TCBS từ chối dù HTTP là 200
```

**Khi có JWT:** đo tập `rc` thật của `deposit` / `withdraw` / `transfer` / `cancel-condition`,
rồi quyết định có nên raise. Nếu không, cần ít nhất một bậc cảnh báo.

### 1.4 🟡 Nợ kỹ thuật có sẵn

| # | Việc | Vị trí | Ghi chú |
|---|---|---|---|
| N4 | Tách `derivatives.py` **852L — đã vượt** | `vnbroker/broker/tcbs/derivatives.py` | Round 2 **không** thêm dòng nào. Tách ra sẽ giải quyết luôn N7 |
| N7 | Gỡ `requestId` **hư cấu** (spec có **0** lần) | `equity.py:523-525`, `derivatives.py:702-705` | Làm cùng N4 được |
| N8 | Gộp **5 bản `_post`** trùng nhau | `derivatives.py`, `equity.py`, `money.py`, `condition_orders.py`, `_write_http.py` | Round 2 đã tạo `_write_http.py` (155L) làm nền; `condition_orders.py` chưa chuyển |
| — | `equity.py` 798L · `quote.py` 793L · `websocket.py` 791L | | Chỉ còn 2–9L dưới ngân sách — thêm 1 method là vượt im lặng |
| — | `auth.py:271-273` ghi `token_expires_at` **ngoài lock** (race) | Round 2 audit F-4, minor | `session.py` ngoài phạm vi round 2 |
| — | `token_expires_at=None` ⇒ `check_and_update_state()` lập tức `EXPIRED` | Round 2 audit F-5, minor | Hiện **0 caller** — bẫy đang ngủ |
| — | `guards.py:56` trả `kwargs_keys` ra envelope dry-run | Round 2 audit F-9, minor | Lộ **tên** field nhạy cảm (`pin`/`otp`) vào log nếu caller in envelope |

### 1.5 🟡 Gỡ `/aion/v1/accounts` — cân nhắc lại
Owner đã chốt **giữ làm ngoại lệ** (vì gỡ sẽ phá `@abstractmethod get_account_list`).
Path thay thế `/aion/v1/customers/{custodyId}/accounts` cần `custodyId` — tức là cần
**chính thông tin mà method đó sinh ra**. Khi đã có JWT thì `custodyId` sẽ lấy được
từ đâu đó; xem lại khi đó.

---

## 2. Bản đồ code sau Round 2

```
vnbroker/broker/tcbs/
  token_manager.py      303L  MỚI  · decode JWT cục bộ, cache, token_provider, on_expiring
  _write_http.py        155L  MỚI  · POST + map 400/404/422/429 + describe_business_code
  condition_orders.py   187L  MỚI  · huỷ lệnh điều kiện phái sinh
  auth.py               306L  · +apikey/info, +apikey/extend, hạn lấy từ claim exp
  money.py              773L  · +pricing-policy, +deposit/withdraw/transfer (write gate)
  client.py             772L  · facade: +7 wrapper, wire ConditionOrderService
  derivatives.py        852L  ⚠ ĐÃ VƯỢT 800L — cấm thêm dòng
  equity.py             798L  ⚠ chỉ còn 2L
vnbroker/explorer/tcbs/
  listing.py            421L  · +ananke/v1/securities (raw dict, shape chưa tài liệu hoá)

docs/references/openapi-v1.0.0.json   spec chính thức, sha256 7f97d27b…42bd4a
scripts/verify_tcbs_coverage.py       in/out phủ API (TỰ kiểm sha256)
```

**Hợp đồng spec:** path trong code **phải** khớp `paths` của
`docs/references/openapi-v1.0.0.json`. Đổi spec ⇒ chạy lại `verify_tcbs_coverage.py`
trước khi sửa code.

## 3. Gate để dùng lại

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider   # 3 phút
.venv\Scripts\python.exe -m pytest tests/contract -q -p no:cacheprovider        # 72
.venv\Scripts\python.exe -m ruff check vnbroker
.venv\Scripts\python.exe scripts/check_mypy_baseline.py
.venv\Scripts\python.exe -m ruff check tests          # 13 KNOWN-RED, không được tăng
.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py
```

⚠ **Đừng chạy `pytest tests/contract` trong worktree khi chưa merge** — nó không phải
contract test của TCBS (thư mục đó **0 file TCBS**).

⚠ **`test_news_integration.py` gọi mạng thật** `kbbuddywts.kbsec.com.vn` và **flaky**
(read timeout 30s). Đây là lần thứ 3 trong 2 đợt mà một lần chạy đơn lẻ dẫn tới kết
luận sai. **Chạy lại lần hai trước khi báo đỏ.**

## 4. Quy trình — kinh nghiệm từ Round 2

1. **Đếm bằng script, đừng đọc bằng mắt.** "13 endpoint chưa dùng" sai 4; `requestId`
   là bịa; `expiredTime` không tồn tại. Cả 3 lỗi đều lộ ra khi quét AST trên spec.
2. **Spec phải nằm trong repo.** Đợt 1 chạy được nhưng không ai tái lập lại được vì
   spec chỉ ở `~/Downloads`.
3. **`.env` không vào worktree** ⇒ baseline đo trong worktree khác main tree. Đừng ép
   khớp số, hãy ghi rõ số nào đo ở đâu.
4. **Đừng tin lời agent** — 3 agent đều báo "AC đạt hết" và đều đúng về AC, nhưng
   **2 lỗi major nằm ngoài AC** chỉ lộ ra khi audit đọc code.
5. **Bằng chứng fail-trước phải chạm đúng tầng lỗi.** Assert cấu trúc là bằng chứng
   vô giá trị; phải chạy code thật với input gây lỗi thật.
6. **`docs/PLAN_<T>.md` → `PLAN_AUDIT` phải `PASS`/`AGREE` trước khi giao agent.**

## 5. Việc admin

- Branch `feat/t-token` · `feat/m-money` · `feat/e-cond-sec` **đã xoá local** (chúng chỉ
  tồn tại local, chưa push). **Không mất gì**: cả 3 đã merge vào `dev` bằng **merge commit**
  riêng nên vẫn revert được từng lát:
  ```powershell
  git revert 090034a   # lát T  · TokenManager + 2 endpoint gaia
  git revert 90ead64   # lát M  · 4 endpoint tiền/vay
  git revert 8e4f959   # lát E  · condition/cancel + ananke securities
  git revert f23786f   # wire facade + __init__
  git revert bc9d786   # fix audit F-1/F-2
  ```
- Worktree `../tcbs-t-token` · `../tcbs-m-money` · `../tcbs-e-cond-sec` **đã gỡ sạch**
  (junction `.venv` đã gỡ trước, main `.venv` còn nguyên 255320 B).
- Branch đợt 1 `feat/a1-bars` · `feat/a2-ws` · `feat/a3-legacy` + `docs/plan-tcbs`
  **vẫn còn** local/remote — đã merge ở đợt 1, có thể xoá.
- **CI GitHub Actions vẫn không chạy** (job bị từ chối do billing). Mọi gate phải
  chạy local qua lệnh ở §3.