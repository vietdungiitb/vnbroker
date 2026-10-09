# Bàn giao — TCBS Rebuild, đợt 1 (3 lát)

**Ngày:** 2026-10-09 · **Trạng thái:** merged vào `dev`, gate xanh, **chưa probe server thật**
**Bản chất:** 3 lát chạy song song qua skill `multi-agent-workflow` (Mode A).

> **Câu đầu tiên phải đọc:** đợt này **CHƯA** đạt mục tiêu "phủ hết API TCBS". Đã
> xong 3 lát đầu (nối OHLCV · viết lại WebSocket · gỡ path legacy). **Còn nợ GĐ4
> TokenManager và GĐ5 13 endpoint.**

---

## 1. Nguyên nhân gốc: vì sao phải làm

`vnbroker` đã hỗ trợ TCBS nhưng code viết theo **API cũ (erebos/aion)** và **tầng
wire sai hoàn toàn**. Đối chiếu 2 tài liệu chính thức (48 REST + 5 WebSocket,
khớp nhau 48/48) ra 3 lỗi hệ thống:

| # | Lỗi | Mức |
|---|---|---|
| **F1** | `websocket.py` gửi **JSON**, protocol chính thức là **TEXT frame phân tách `\|`**. Auth sai (header thay vì frame), sai thứ tự auth/subscribe, heartbeat sai, không tắt auto-ping | Client **không thể xác thực** |
| **F2** | `history()` ném `NotImplementedError` cho daily OHLCV với lý do **sai** ("TCBS chỉ có intraday tick data") — trong khi spec có `bars-long-term` D/W/M | Tính năng chết |
| **F3** | 18 path không có trong bất kỳ tài liệu nào | Bẩn, chết |

## 2. Commit

| Agent | Nội dung | Commit |
|---|---|---|
| a1 | `feat(tcbs)`: nối 2 endpoint OHLCV | `6c88f4b` |
| a2 | `feat(tcbs-ws)`: viết lại WebSocket theo protocol thesis | `f2ba384` |
| a3 | `refactor(tcbs)`: gỡ 18 path legacy | `de4c7f8` |
| coordinator | `test(tcbs)`: sửa 2 fixture về shape spec | `a832a84` |

## 3. Gate — đo local (`scripts/check_all.ps1`)

> CI GitHub Actions **không chạy** (job bị từ chối do billing). Dùng kết quả local.

| Gate | Baseline @ `bec8b82` | Sau merge @ `a832a84` |
|---|---|---|
| `pytest tests/ -q` | 1497 passed, 26 skipped | **1696 passed, 26 skipped** (**+199**) |
| `pytest tests/contract` | 72 passed | 72 passed |
| `ruff check vnbroker` | exit 0 | exit 0 |
| `scripts/check_mypy_baseline.py` | exit 0 (1266) | exit 0 (**1161**, fix 105) |
| `ruff check tests` | 13 KNOWN-RED | 13 KNOWN-RED (**không tăng**) |

Tái lập:
```powershell
pwsh -File scripts/check_all.ps1
```

**Ngân sách 800L** (`CLAUDE.md:15`): khối TCBS còn đúng 1 file vượt —
`derivatives.py` 852L (có sẵn, ngoài phạm vi lát này). `quote.py` 801→**793L**,
`account.py` 937→**489L**, `equity.py` 980→**798L**, `websocket.py` 412→**791L**.

## 4. Tự kiểm chứng (coordinator, **không** tin báo cáo agent)

### ⚠ Bằng chứng cụ thể cho hazard "gate không đại diện máy khác"
Sau khi merge vào `dev` (`5813327`), `check_all.ps1` chạy **FAIL 1 test**
(`1 failed, 1695 passed, 26 skipped`). Chạy lại `pytest` trực tiếp: **0 đỏ**
(`1695 passed, 27 skipped`) — test bị chuyển sang skip là
`tests/integration/test_news_integration.py`, gọi mạng thật
`kbbuddywts.kbsec.com.vn` và **read timeout 30s**. Chạy lại `check_all.ps1`
lần nữa: **PASS, `1696 passed, 26 skipped`**.

⇒ Đây là **flake do mạng**, không phải lỗi code. Nhưng suýt đã khiến tôi báo
PASS một cách không trung thực nếu chỉ nhìn 1 lần chạy. Đã ghi lại vì đây là
lần thứ hai trong đợt này cùng một dạng bẫu (lần trước: fixture nằm ngoài
khoảng ngày của test).

**Số liệu `1696 passed / 26 skipped` trong bảng §3 là của lần chạy PASS thứ hai.**

### AC S1 — kiểm bằng payload thật Owner đã paste (có `dataT1: null`)
```
cot      : ['time', 'open', 'high', 'low', 'close', 'volume']
tz       : Asia/Ho_Chi_Minh
dau      : 2025-09-12 07:00:00+07:00
ngay     : ['2025-09-12', '2025-09-15']
dataT1 lot tu frame? False
```
⇒ AC#1 cột chuẩn ✓ · AC#2 tz VN ✓ · AC#3 ngày không dịch ✓ · AC#4 field lạ `.get()` ✓
AC#7 map `D/W/M` riêng ✓ (`1D→D`, `1W→W`, `1M→M`; interval lạ → `ValueError`)

### AC S2 — đọc code thật
`d|a|||` (`websocket.py:194`) · `d|p|||` (`:199`) · `ping_interval=None` ·
**bảng `_WS_ENDPOINTS_SIT` đã bị xoá hẳn** (chỉ còn comment giải thích DNS fail) ·
`use_sit` giữ chữ ký + cảnh báo bị bỏ qua. `json.loads` còn lại ở `:275,:300` là
**đúng** — đó là payload *sau* tiền tố `s|CHANNEL|`, không phải cả frame.

### AC S3 — đếm bằng script khoanh đúng khối `{}`
`_REMOVED_PATHS` = **18** path · đối chiếu `openapi-v1.0.0.json`: **18/18 vắng mặt** ✓ ·
`_PATHS` còn **39** path sống.

### Sự cố khi tự kiểm chứng (đáng ghi lại)
Lần verify **thứ nhất của tôi FAIL** (`ImportError: parse_long_term_bars`) — tôi đoán
tên hàm thay vì đọc `bars.py`. Lần thứ hai dùng regex không khoanh đúng dict, quét
lấy cả `_REMOVED_PATHS` ⇒ báo động giả "path legacy còn sống". Lần thứ ba mới khoanh
đúng khối `{}`. **Ba lần, ba kết luận khác nhau — không lần nào từ lời agent.**

## 5. ⚠ Đính chính — lỗi của chính audit của tôi

Tôi từng phát biểu: *"19 path legacy là những path có tiền tố `erebos`/`aion`"*.

**Tiêu chí này sai.** Spec chính thức **có** các endpoint dùng đúng các tiền tố đó:
- `/erebos/v2/digital/margin-info` (`money.py:margin`) — có trong spec **và** Postman
- `/erebos/v2/digital/trans-hist-cashStatements` (`money.py:cash_statements`) — có ở cả hai
- `/eros/v2/get-profile/by-username/{custodyCode}` — thật

18 path đã gỡ được **xác minh riêng từng cái** là vắng trong spec, nên kết quả gỡ
đúng. **Nếu tôi tin tiêu chí cũ thì đã xoá nhầm 2 path đang hoạt động.**
Bài học: tiêu chí lọc phải là **vắng ở path cụ thể**, không phải **vắng ở tiền tố**.

## 6. CHƯA CHẠY — không được ghi là PASS

| Việc | Vì sao chưa chạy |
|---|---|
| **Probe server TCBS thật** | Chưa có JWT. `.env` chỉ có `TCBS_AUTH_TOKEN` = 48 ký tự tiền tố `10000928...` — đó là **API key**, không phải JWT (JWT phải 3 phần). `apikey/info` → 200 (key hạn 2027-05-19); `oauth2/token` với OTP giả → 400 `203033 Invalid OTP` (key được chấp nhận). Cần **Smart OTP từ app TCInvest**. Lệnh đã lưu: `pwsh -File "$env:TEMP\getjwt.ps1"` |
| **Xác nhận 18 path legacy chết trên server** | 401 chạy trước routing ⇒ có token cũng không phân biệt được route có hay không. Gỡ là **quyết định Owner dựa trên 2 tài liệu**, chưa probe |
| **`countBack` + map resolution phút** | Spec không nói cách ánh xạ khoảng ngày → số nến. Đang dùng **hệ số ước lượng** (`_TRADING_DAY_RATIO = 0.70`, 330 nến/phiên). Phải đo lại khi có JWT |
| **Frame WebSocket thật** | Test lấy frame từ **tài liệu**, không phải capture. `_reconnect()` cũng cần server |
| **CI GitHub Actions** | Job bị từ chối do billing |

## 7. Quyết định của Owner trong đợt này

| # | Câu hỏi | Chốt |
|---|---|---|
| 1 | Gỡ `/aion/v1/accounts` sẽ phá `@abstractmethod get_account_list()` (`broker/base.py:55`) | **Giữ làm ngoại lệ**, ghi rõ lý do |
| 2 | Merge đợt này hay chờ làm đủ | **Merge + bàn giao phần còn lại** |
| 3 | Push GitHub | **Merge vào `dev` + push origin** |

**Về ngoại lệ #1:** path thay thế `/aion/v1/customers/{custodyId}/accounts` cần
`custodyId` — tức là cần **chính thông tin mà method đó sinh ra**. Gỡ ⇒
`TCBSBrokerClient` thành abstract. Xem `broker/tcbs/account.py:26` và `:57`.

## 8. Còn nợ — thứ tự đề xuất

1. **Lấy JWT** (Smart OTP từ TCInvest) ⇒ bật được probe server thật.
   Đây là **nút thắt** chặn mọi xác minh còn lại.
2. **Đo lại `countBack`/resolution** bằng dữ liệu thật, thay hệ số ước lượng.
3. **Probe 18 path đã gỡ.** Nếu chúng **vẫn sống** → `git revert de4c7f8` là đủ.
4. **GĐ4 TokenManager** — JWT sống 8 giờ, hiện không có cơ chế refresh.
5. **GĐ5 — 13 endpoint** spec chưa dùng.
6. `derivatives.py` 852L → tách dưới 800L.
7. Cân nhắc lại `/aion/v1/accounts` khi đã có JWT.

## 9. Rollback

Mỗi lát là branch độc lập, revert được riêng:
```powershell
git revert de4c7f8   # chỉ gỡ path legacy
git revert f2ba384   # chỉ trả WebSocket về bản cũ
git revert 6c88f4b   # chỉ bỏ bars
```
Worktree đã dọn; branch `feat/*` giữ lại đến khi Owner đồng ý xoá.

## 10. Bài học cho session sau

1. **Không tin lời agent** — tôi verify 3 lát bằng script riêng và tìm ra 1 lỗi
   trong chính audit của mình (§5). Cùng một lần verify tôi hỏng 3 lần vì đoán
   tên hàm và quét regex không khoanh đúng dict.
2. **Worktree không có `.env`** (file bị gitignore) ⇒ baseline trong worktree khác
   main tree. Cả 3 agent đều tự đo baseline của worktree thay vì ép khớp số của main
   — **làm đúng**, vì con số 1497/26 của main tree không tái lập được ở đó.
3. **Fixture cũ có thể mã hoá hợp đồng đã chết.** 4 test đỏ sau khi gỡ path là vì
   chúng mock shape intraday tick `{t,p,v,a}`. Khi sửa fixture, **đọc cả khoảng dữ
   liệu test yêu cầu** — tôi sửa 2 lần: lần 1 đặt nến ngoài `[start, end]` của test.
4. **File ngoài claim là nơi lỗi nấp.** 2 path `/erebos/v2/digital/*` trong `money.py`
   suýt bị xoá nhầm vì `money.py` không nằm trong bất kỳ claim nào.
