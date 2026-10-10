# HANDOVER — Tier-1 Wave 3 + Wave 4 (bàn giao cho session sau)

**Trạng thái:** đã merge vào `main`, đã push, tag `v3.7.0`.
**Cổng vào duy nhất:** `pwsh -File scripts/check_all.ps1` — **exit 0** ở trạng thái này.
**Lessons áp dụng:** L-E01 · L-E02 · L-E03 · L-E04 · L-E06 · L-E07 · L-P01 · L-P02 ·
L-P03 · L-P04 · L-P05 · L-P06 · L-R01 · L-R03 · L-R07

---

## 1. NHẬT KÝ CÔNG VIỆC ĐÃ HOÀN THÀNH

### 1.1 Commit trên `main`

| Commit | Nội dung |
|:--|:--|
| `0b2c9ba` | Plan + audit vòng 1&2 + claim (base `4cd0f2d`) |
| `1025bd6` | **merge W3** — rate-limit thật |
| `cc41be2` | **merge T4** — logger không rò token |
| `3fb4415` | 4 minor + major (`VERSION_NOTICES` + bump **3.7.0**) |
| — | 2 minor residual của `3fb4415` (xem §3) |

Cây: `main` ← `feat/w34-ratelimit` + `feat/w34-logger`, cả hai từ `refs/heads/main`.
⚠ Dùng `refs/heads/main` trần: repo có branch `main` **và** remote-tracking `main`
nên `main` trần bị **ambiguous** và `git checkout -b … main` fail.

### 1.2 Vấn đề đã sửa — kèm bằng chứng đo trước/sau

| # | Vấn đề | Trước | Sau | Nguyên nhân gốc (đo) |
|:--|:--|:--|:--|:--|
| 1 | **429 bị retry** | **3** request/lệnh (cố định) · **6** (AUTO, 2 provider) | **1** · **2** | `tenacity` ở `base.py` và `common/data.py` retry **mọi** `ConnectionError`, 429 nằm trong đó |
| 2 | **`RateLimitError` làm failover chết** | `should_failover == False` | `True` | `RateLimitError(NetworkError)` **không** có `OSError` trong MRO; `should_failover` xét `isinstance` **trước**, marker `"429"` không có trong chuỗi *"throttled requests"* |
| 3 | **Cooldown bỏ qua `Retry-After`** | `4.935s` (suy đoán `5·2^(n−1)`) | `119.93s` | `send_request_direct` **không** chạm `response.headers`; `rg 'response\.headers' vnbroker/` → **1** hit, thuộc DNSE |
| 4 | **Logger rò token** | **4/10** chuỗi thử | **0/10** | `SENSITIVE_PATTERN` đòi `key<sep>value`, lớp giá trị `[^"\',\s}]+` **dừng ở dấu cách** ⇒ `Authorization: Bearer <JWT>` chỉ ăn `Bearer` |
| 5 | **`log.info("%s", dict)` mất dòng log** | `TypeError` ⇒ **mất trọn dòng** | `x={'a': 1, 'b': 2}` | Python 3.13 bóc `args=({...},)` thành dict; filter duyệt ra **key** |
| 6 | **Redact quá rộng** | `monkey=abc` → `'monkey: "***REDACTED***"'` | giữ nguyên | regex **không có word boundary**; `key` khớp giữa từ |
| 7 | **`bearer` tiếng Anh bị bóp méo** | (do đợt này tạo ra, audit bắt) | giữ nguyên | rule Bearer khớp "scheme + bất kỳ từ nào"; đúng dạng **L-R07** |
| 8 | **URL 429 lộ query string** | `url=…?api_key=SECRET` | `url=https://api.example.vn/quote` | HMAC provider (DNSE, KBS) ký bằng query string |
| 9 | **`retry_after` mất ở PROXY+TRY** | bọc `ConnectionError("All proxies failed")` | giữ `RateLimitError` | mỗi proxy thất bị bọc lại |
| 10 | **`Retry-After: 0.5` in `0 seconds`** | sai | `0.5 seconds` | `int()` cắt phần thập phân |

### 1.3 Kiểm chứng bằng dữ liệu đo được (không suy luận)

Tất cả đo bằng **call counter** và **chạy thật** `redact_sensitive_data()`:

| Lệnh | Trước `4cd0f2d` | Sau |
|:--|:--|:--|
| 429, source cố định, số HTTP attempt | **3** | **1** |
| 429, AUTO 2 provider, số HTTP attempt | **6** | **2** |
| `should_failover(RateLimitError('kbs', retry_after=120))` | **False** | **True** |
| `cooldown_remaining_sec` với `Retry-After: 120` | **4.935** | **119.93** |
| 10 chuỗi log thử, số rò token | **4** | **0** |
| 6 chuỗi phải giữ nguyên, số bị bóp méo | **1** | **0** |
| `log.info("x=%s", {"a":1,"b":2})` | **mất dòng log** | in đúng |

---

## 2. ĐÍNH CHÍNH — những điều **tôi** nói sai ở đợt trước và trong đợt này

Ghi lại vì tài liệu cũ còn đọc dễ tin (L-E01).

| Điều đã nói | Thực tế | Bằng chứng |
|:--|:--|:--|
| "**11** file vượt 800L" (`HANDOFF_TIER1_WAVE12.md:167`) | **10** trong `vnbroker/`; **12** cả repo | `python -c "…rglob('*.py')…len(splitlines())"`, lọc theo thư mục |
| `common/data.py` = **1876** dòng | **1823** | như trên |
| "**15** test bảo về token-bucket chết" | **0** test gọi `configure_rate_limiter`/`get_rate_limiter`; `TokenBucketRateLimiter` **đang chạy thật** ở `async_client.py:90` | đếm bằng script |
| "**75** call site `send_request`" | **58** call + 9 import (AST); 75 là đếm **chuỗi thô** | script AST |
| "8 PASS" của `check_all.ps1` | **9 PASS** | chạy thật |
| **`common.data.Quote` không retry 429** (kế hoạch v2 của chính tôi) | **SAI** — retry nằm **bên trong** `_run_with_failover`, không phải decorator. Đo lại: **3** và **6** | `common/data.py:647-656`, `:665-674` |
| "`explorer/tcbs/auth.py` dùng logger rò" | File này **không có logger** (106 dòng, đọc token từ env rồi không log) | `git grep get_logger` |
| "`broker/ssi/auth.py` đi qua logger này" | Dùng `logging.getLogger` chuẩn; `SensitiveDataFilter` **không** gắn ở đó | `core/utils/logger.py:106` là chỗ gắn duy nhất |

⚠ **Đếm bằng PowerShell làm sai số.** `Get-Content | Measure-Object -Line` cho
**1583** dòng với `common/data.py` trong khi `len(splitlines())` cho **1823**.
Luôn dùng Python.

---

## 3. HAI THỨ ĐÃ SỬA NHƯNG CẦN NÓI THẳNG

| Việc | Tình trạng |
|:--|:--|
| `Bearer <token ≤15 ký tự>` **không** còn bị che | **Đánh đổi có chủ ý** (L-R07): bắt nó sẽ phá prose (`'bearer of the bond coupon'`). Ghi trong comment `logger.py` + `CHANGELOG.md` |
| `explorer/dnse/quote.py:139-140` `_raise_for_failover` viết lại mọi `ConnectionError` thành `ConnectionError` thuần | **Mất `retry_after`.** DNSE hiện **không** đi qua `send_request_direct` nên chưa kích hoạt — nợ N11 |

---

## 4. CÒN TỒN ĐỌNG

### P0 — ảnh hưởng người dùng

| # | Việc | Bằng chứng | Trạng thái |
|:--|:--|:--|:--|
| **B1** | **Loại `intraday` của TCBS khỏi AUTO** (Owner **đã chọn**, chưa làm) | server trả `"a": ""` cho **mọi** bản ghi ⇒ `match_type` toàn `unknown` | ⛔ `ProviderPool.AUTH_PROVIDERS['tcbs']['supports']` là danh sách **module**, còn `intraday` là **method** ⇒ cần bảng loại theo method + quy tắc C6 mới cho `check_provider_consistency.py`. **Cần Owner xác nhận lại** vì đây là thay đổi hành vi `AUTO` |
| **B2** | **DNSE không tới được** | `ConnectionResetError(10054)` 3/3; TLS handshake `openapi.dnse.com.vn` **timeout** | **CHƯA CHẠY** ở tầng mạng. **Đừng** kết luận "DNSE hỏng" |

### P1 — cần Owner quyết

| # | Việc | Vì sao chưa làm |
|:--|:--|:--|
| **A1** | `.env` tự nạp — Owner chọn hướng **opt-in qua env flag** | cần `python-dotenv` hoặc bộ đọc tay; thêm phụ thuộc là quyết định riêng (nợ N7) |
| **A2** | Benchmark p99 latency + tỉ lệ lỗi để quyết thứ tự `AUTO` | Owner chọn "đo rồi mới quyết" nhưng **chưa** có số đo. Hiện provider có credential **nối cuối** — giữ nguyên là quyết định có chủ ý |
| **B1** | xem lại dòng trên | — |

### P2 — nợ kỹ thuật

| # | Việc | Số đo |
|:--|:--|:--|
| **N1** | 36/40 `@retry` trong `api/*.py` không `reraise=True` **và không có `retry=`** ⇒ retry **mọi** exception, người dùng nhận `tenacity.RetryError` thay vì lỗi gốc | script AST; `base.py:233` đã dùng predicate composite — 36 chỗ kia thì chưa |
| **N2** | T1 — 10 file >800L trong `vnbroker/` (`common/data.py` 1823L) | Owner không chọn |
| **N3** | T2 — 13 lỗi `ruff check tests` (KNOWN-RED) | có sẵn từ `9d5db1d` |
| **N4** | T3 — mypy 1138 lỗi | baseline gate, giảm dần |
| **N5** | A3 — screener VCI/KBS trả 0 dòng | Owner không chọn |
| **N6** | A2 — benchmark (xem P1) | — |
| **N7** | A1 — `.env` opt-in (xem P1) | — |
| **N8** | B1 — `intraday` TCBS (xem P0) | — |
| **N9** | `common/data.py:197-203` định nghĩa class `Config` **thứ hai** (`DEFAULT_RETRIES = 3`), trùng khái niệm với `vnbroker/config.py` | `python -c "from vnbroker.config import Config; print(hasattr(Config,'DEFAULT_RETRIES'))"` → `False` |
| **N10** | `Retry-After` dạng HTTP-date chưa xử lý | cố ý: không provider nào gửi dạng đó |
| **N11** | `explorer/dnse/quote.py:139` mất `retry_after` | xem §3 |
| **N12** | `broker/ssi/auth.py` dùng `logging.getLogger` chuẩn ⇒ **không** đi qua `SensitiveDataFilter` | lane tiền thật — **ưu tiên cao** khi làm lát sau |
| **N13** | `broker/tcbs/auth.py` debug log chưa redact (`_logger.debug`, token trong response) | **chưa kiểm đủ**; kiểm trước khi đụng |

---

## 5. CÁI GÌ ĐÃ TỐN THỜI GIAN NHẤT — ĐỪNG LÀM LẠI

### 5.1 Đếm sai ⇒ tin sai (L-E01)

Cả ba lần trong đợt này, số sai đều đến từ **đếm bằng mắt hoặc đếm chuỗi thô**:
11 file (thực 10) · 75 call site (thực 58) · 15 test (thực 0).

### 5.2 `hasattr` cho kết quả đúng nhưng kết luận sai (hazard 10)

Tôi kiểm `hasattr(Quote.history, 'retry')` → `False`, và **kết luận** "không retry
429". Sai: retry nằm trong `_run_with_failover`. Đo lại bằng call counter mới ra
**3** và **6**.

⇒ **Đếm cái mà AC nói tới.** Đừng kiểm cấu trúc rồi suy ra hành vi.

### 5.3 `git checkout -b <branch> main` fail với *"ambiguous object name"*

Repo có branch `main` **và** remote-tracking `main`. Dùng `refs/heads/main`.

### 5.4 Worktree không có `.env` ⇒ số test khác

Worktree có `.venv` **nhưng không có `.env`** (L-P01). `pytest tests/` trong
worktree ra `1 failed` (`test_dnse_integration` cần `DNSE_API_SECRET`), trong khi
main tree ra `0 failed`. **Đây là khác biệt môi trường, không phải hồi quy.**

### 5.5 Script chạy từ `%TEMP%` import nhầm cây

`sys.path[0]` là thư mục script, nên `import vnbroker` lấy **main checkout** chứ
không phải worktree — script báo "không thay đổi" một lần rồi. Luôn
`sys.path.insert(0, <worktree>)` và in `vnbroker.__file__` **trước** khi tin số.

### 5.6 Regex redact: bảo vệ bằng cách phá dữ liệu thì tệ hơn lỗi nó chặn (L-R07)

Cách tự nhiên bắt `otp 123456` là cho phép dấu cách làm dấu phân cách. Đo được:

```
'the user name is bob'    -> 'the user: "***REDACTED***" is bob'
'key note: read the file' -> 'key: "***REDACTED***" read the file'
```

Cách đúng: **neo chữ số** (4–8 digit) + **word boundary** quanh tên biến. Và
`Bearer` cũng phải đòi token **có hình dạng credential**, nếu không nó ăn tiếng
Anh thường.

---

## 6. CHECKLIST CHO SESSION SAU

```powershell
# 0. Bắt buộc đặt trước khi in bất cứ thứ gì có dấu tiếng Việt
$env:PYTHONIOENCODING="utf-8"     # console cp1252 -> UnicodeEncodeError

# 1. Cổng đầy đủ (KHÔNG dùng -Quick trước khi merge)
pwsh -File scripts\check_all.ps1
#    kỳ vọng: 9 PASS · 1 KNOWN-RED (ruff-tests-all) · 0 FAIL · exit 0

# 2. Cổng mới + tự kiểm chính nó
.venv\Scripts\python.exe scripts\check_provider_consistency.py
.venv\Scripts\python.exe scripts\check_provider_consistency.py --self-test
```

Trước khi viết plan, **bắt buộc** nạp skill `project-lessons` và đọc
`docs/LESSONS/{evidence,process,broker-risk}.md` theo tag; mọi plan phải có dòng
`Lessons áp dụng: [...]`.

Trước khi sửa `vnbroker/broker/**` (tiền thật): **bắt buộc** đọc
`docs/LESSONS/broker-risk.md`.

⚠ **Đừng tin số trong tài liệu cũ.** `HANDOFF_TIER1_WAVE12.md` §5 còn ghi
"11 file", "1876 dòng", "15 test" — cả ba sai. Đo lại.

---

## 7. GỢI Ý LÁT TIẾP THEO

**Ưu tiên 1 — N12** (`broker/ssi/auth.py` không qua `SensitiveDataFilter`). Đây là
logger của **lane tiền thật**; đợt này vá logger nhưng SSI lane không đi qua nó.

**Ưu tiên 2 — B1** (loại `intraday` TCBS khỏi AUTO). Owner đã chọn hướng, nhưng
cần thêm quy tắc C6 cho `check_provider_consistency.py` để không tái phát.

**Ưu tiên 3 — A2** (benchmark p99). Không có số đo thì không ai lên đầu `AUTO`.

**Ưu tiên 4 — N1** (36 `@retry` không `reraise`). Người dùng đang nhận
`tenacity.RetryError` thay vì lỗi gốc — và `should_failover(RetryError)` chỉ
**tình cờ** `True` qua chuỗi `"raised ConnectionError"`. Đổi tên class là
failover chết.

---

## 8. BẰNG CHỨNG ĐỂ TÁI LẬP TOÀN BỘ

Script đo nằm ở `%TEMP%\opencode\` của máy Owner: `recheck_attempts.py`
(đường người dùng thật), `verify_fixes.py` (5 minor), `probe_args.py` (lỗi
`record.args`), `probe_worktree.py` (xác nhận worktree tự import của nó).

Chúng **không** commit vào repo vì đọc credential thật. Nếu muốn giữ lâu dài thì
chuyển thành script trong `scripts/` với `.env` tổng hợp — và cần Owner duyệt vì
đọc credential.