# PLAN — Tier-1 Wave 3 + Wave 4: rate-limit thật và logger không rò token

**Ngày:** 2026-10-10 · **Base:** `refs/heads/main @ 4cd0f2d` (đo lại, không lấy từ tài liệu cũ)
**Kế hoạch cha:** `docs/PLAN_TIER1_PROVIDER_AGNOSTIC.md` §6 (Wave 3) ·
`docs/HANDOFF_TIER1_WAVE12.md` §5 (T4)
**Audit kế hoạch:** `docs/PLAN_AUDIT_TIER1_WAVE34.md` — `NEED_REVISION`, `confidence: high`
**Lessons áp dụng:** L-E01 · L-E02 · L-E03 · L-E04 · L-E06 · L-E07 · L-P01 · L-P02 · L-P03 · L-P04 · L-P05 · L-P06 · L-R01 · L-R03 · L-R07

> **Bản này đã sửa sau audit vòng 1.** Bản v1 có **1 blocker** (audit finding #15):
> dùng `RateLimitError` sẵn có làm **AUTO failover chết**. Chi tiết ở §1.1.
>
> **Vòng 2 sửa thêm 1 blocker + 4 major.** Bản v2 **tự dẫn đường dẫn người dùng
> sai**: tôi kết luận `common.data.Quote` không retry 429 bằng cách soi
> `hasattr(Quote.history, 'retry')` — nhưng retry **không** nằm ở decorator, nó
> nằm **bên trong** `_run_with_failover`. Đo lại: **3** attempt (source cố định) và
> **6** attempt (AUTO, 2 provider cùng 429). Chi tiết ở §1.2.

---

## 0.1b Sửa sau audit — 5 chỗ, mỗi chỗ có bằng chứng

| # | Audit finding | Bản v1 nói | Bản v2 nói | Bằng chứng |
|:--|:--|:--|:--|:--|
| **15** | **BLOCKER** | "`should_failover` **đã** trả `True` cho `429` ⇒ failover không cần sửa" | `RateLimitError` **không** phải `OSError` ⇒ `should_failover(RateLimitError('kbs', retry_after=120)) == **False**`. Thay class là **làm failover chết**. Phải cho nó kế thừa `ConnectionError` **trước** khi dùng | đo @ `4cd0f2d`: `MRO=[RateLimitError, NetworkError, vnbrokerError, Exception]` · `isinstance(OSError)=False` · `should_failover=False`. Sau khi sửa: `should_failover=True`, `isinstance(ConnectionError)=True` |
| **6/17** | major | AC-3.2/AC-3.4 viết trên `history()` của `api/quote.py` — nhưng 36 decorator kia **không** có `reraise` **và không có `retry=`** ⇒ retry **mọi** exception ⇒ AC **không thi hành được trong phạm vi** | Đo lại: `common.data.Quote.history` (đường người dùng thật qua `Vnbroker.stock()`) **không** có wrapper tenacity. AC chuyển sang đo trên **đường thật** đó | `python -c "…common.data.Quote.history.__module__…hasattr(...,'retry')"` → `False` |
| **19** | major (L-R07) | T4.4 "cho phép dấu cách làm dấu phân cách" | Cách đó **phá huỷ dữ liệu**: `'the user name is bob'` → `'the user: "***REDACTED***" is bob'` (do `SENSITIVE_KEYS` chứa `user`, `key`, `auth`). Dùng **word-boundary + neo chữ số** thay thế | đo trên bản v1 của regex: 2/2 câu tiếng Anh bị ăn. Bản sửa: **11/11** ca đúng (4 phải redact, 7 phải giữ nguyên) |
| **7** | major | "`explorer/tcbs/auth.py` … đây là logger của lane tiền thật" | `explorer/tcbs/auth.py` **không có logger nào** (106 dòng, đọc token từ env rồi không log). `broker/ssi/auth.py` dùng `logging.getLogger` chuẩn, **không** đi qua `SensitiveDataFilter`. Chỉ `connector/dnse/trade.py` (đặt lệnh) dùng logger này | `git grep -n get_logger 4cd0f2d -- vnbroker/explorer/tcbs/auth.py vnbroker/broker/ssi/auth.py vnbroker/connector/dnse/trade.py` |
| **17** | major | AC-4.3 chỉ nói string-arg; **T4.3 (args không phải str) không có AC** | Thêm **AC-4.4**; thêm ca `monkey=abc` vào AC-4.2 vì đó là **lỗi quá rộng đang sống** | đo: `redact_sensitive_data('monkey=abc')` → `'monkey: "***REDACTED***"'` — regex **không có word boundary** |

Ngoài ra: số "**75** call site" của audit v1 là **đếm chuỗi thô**, không phải
call site (AST cho **58**); "8 PASS" của `check_all.ps1` thực ra là **9 PASS**;
"10 file >800L" chỉ đúng khi giới hạn trong `vnbroker/` (cả repo = **12**).
Cả ba đã sửa ở §0 và §1.

---

## 0. BASELINE — đo lại ở `4cd0f2d`, không đọc số từ tài liệu cũ

Hazard 6: **không đòi PASS của một gate vốn đang đỏ.** Mọi dòng dưới đây có lệnh tái lập.

| Gate | Lệnh thật | Exit @ `4cd0f2d` |
|:--|:--|:--|
| Tổng thể | `pwsh -File scripts/check_all.ps1` | **0** — **9 PASS** · 1 KNOWN-RED |
| ruff src | `python -m ruff check vnbroker scripts tests/unit tests/contract` | **0** |
| ruff tests-all | `python -m ruff check tests` | **1** — 13 lỗi (KNOWN-RED) |
| mypy baseline | `python scripts/check_mypy_baseline.py` | **0** (baseline 1266 → now 1138) |
| contract | `python -m pytest tests/contract -q` | **0** — 91 passed |
| pytest toàn bộ | `python -m pytest tests/ -q --timeout=300` | **0** — 1978 passed, 26 skipped |

⚠ `mypy vnbroker --strict` **không** phải gate (1207 lỗi có sẵn, `--strict` là no-op —
xem `CLAUDE.md`).

### 0.1 Hai CON SỐ trong tài liệu cũ đã hỏng (L-E01 — ghi lại để không tin lần nữa)

| Tài liệu cũ ghi | Đo lại @ `4cd0f2d` | Lệnh tái lập |
|:--|:--|:--|
| "**11** file vượt 800L" (`HANDOFF_TIER1_WAVE12.md:167`) | **10** trong `vnbroker/`; **12** cả repo (2 file trong `tests/`) | `python -c "…rglob('*.py')…len(splitlines())"`, lọc theo thư mục |
| `common/data.py` = **1876** dòng (`HANDOFF…:80`) | **1823** | như trên |
| "**15** test bảo vệ token-bucket chết" (`REPORT_TIER1_EXPLORER_SURVEY.md:166`) | **0** test gọi `configure_rate_limiter`/`get_rate_limiter`; 33 lượt nhắc tên class `TokenBucketRateLimiter` (dùng thật ở `async_client.py:90`) | `python -c "…rglob('*.py')…count()"` |

⇒ Token-bucket **không** phải "code chết được 15 test giữ". Phải đo tiếp trước khi
xoá gì — xem W3.3.

⚠ **Nguyên tắc đếm (sửa sau audit #9/#12):** mỗi số ở đây ghi rõ **phạm vi đo**
(thư mục nào, revision nào) và **dùng công cụ gì**. "75 call site" ở bản v1 là
đếm chuỗi thô; AST cho **58** call thật + 9 import.

---

## 1. NHỮNG GÌ ĐÃ ĐO ĐƯỢC (không suy luận)

### W3.1 — Header rate-limit của server **không được đọc** ở đâu cả

`vnbroker/core/utils/client.py::send_request_direct` là **đường sync mà explorer
đi qua** (đo bằng **AST**, không phải `grep`: **58** lời gọi `send_request*` + 9
import trong `vnbroker/explorer/`; con số "75" là đếm chuỗi thô và đã bị loại).
Nó đọc `response.status_code` rồi `raise ConnectionError(...)` — **không** chạm
`response.headers`. Đo: `git grep -n 'response\.headers' 4cd0f2d -- vnbroker/` →
**1** kết quả, thuộc `connector/dnse/core/http_client.py:158` (lane DNSE).

Hệ quả: `cooldown` chỉ lớn lên theo **suy đoán** `5 * 2**(failures-1)` tại
`source_router.py:367`, không theo `Retry-After` mà server đã trả.

### W3.2 — 429 **bị retry 3 lần** trước kịp chuyển provider ⟵ lỗi nặng nhất đợt này

Đo bằng provider giả ném `ConnectionError("Failed to fetch data: 429 …")`:

| Đường đi | HTTP attempt cho **một** lệnh | Exception cuối |
|:--|:--|:--|
| `base.py::BaseAdapter.history` (có `reraise=True`) | **3** | `ConnectionError` |
| `api/quote.py::Quote.history` (không `reraise`, **không `retry=`**) | **3** | **`tenacity.RetryError`** |
| **`common.data.Quote.history`** (đường người dùng thật) | **1** — không có wrapper tenacity | `ConnectionError` |

⇒ Vì bản cuối **không** retry nên `AC-3.2` **thi hành được** ngay trên đường thật.

Hai vấn đề riêng biệt ở hai đường *không phải* đường chính:

1. **Retry 429 là sai** (`base.py` + `api/*`). Kế hoạch cha §6 W3.2 yêu cầu
   *"không retry khi gặp 429 — chuyển provider ngay"*; hiện tại nó retry **trước**,
   3 lần, xong mới failover.
2. **`RetryError` nuốt nguyên nhân.** 36/40 decorator `@retry` trong `vnbroker/api/`
   không `reraise=True` (đo bằng script AST). Kết quả: người dùng nhận
   `tenacity.RetryError[<Future …>]` thay vì `ConnectionError` — và
   `should_failover(RetryError)` chỉ **tình cờ** `True` vì chuỗi
   `"raised ConnectionError"` chứa marker `"connection"`. Đổi tên class là failover
   chết. (Giữ nguyên như **nợ N1** — ngoài phạm vi.)

### W3.2b — ⚠ BLOCKER đã phát hiện ở audit vòng 1: `RateLimitError` sẽ **làm failover chết**

`vnbroker/core/exceptions.py:292` **đã có** `RateLimitError(NetworkError)`. Bản v1
của plan định dùng lại nó. Đo thì ra:

```
MRO                        : [RateLimitError, NetworkError, vnbrokerError, Exception]
isinstance(e, OSError)     : False
str(e)                     : "[NETWORK_001] Provider 'kbs' temporarily throttled
                             requests. Retry after 120 seconds (...)"
should_failover(e)         : False        <-- FAILOVER CHẾT
should_failover(ConnectionError("... 429")): True
```

Nguyên nhân: `should_failover` (`source_router.py:426`) xét
`isinstance(exc, OSError, NotImplementedError, KeyError, LookupError)` rồi mới xét
15 marker chuỗi. `RateLimitError` không thuộc nhóm nào, và chuỗi của nó ghi
*"throttled requests"* — **không** có `"429"`, **không** có `"rate limit"`.

⇒ Nếu W3.1/W3.4 ném `RateLimitError`, `base.py:180-185` rơi vào nhánh `raise`:
không `record_failure`, không thử provider kế tiếp. **Tệ hơn hiện trạng.**

**Cách sửa (đã kiểm chứng chạy được):** cho `RateLimitError` kế thừa thêm
`ConnectionError`:

```
RateLimitError(NetworkError, ConnectionError)
MRO: RateLimitError → NetworkError → vnbrokerError → ConnectionError → OSError → Exception
isinstance(e, OSError)      : True
isinstance(e, ConnectionError): True
should_failover(e)          : True        <-- failover sống
```

Giữ `NetworkError` để không phá `except vnbrokerError` đang có; thêm
`ConnectionError` để `should_failover` và `tenacity` nhìn thấy nó. **Không** sửa
`should_failover` — sửa class nhỏ hơn và không đổi hợp đồng của hàm.

### W3.3 — Token-bucket: đo lại trước khi kết luận

`configure_rate_limiter` / `get_rate_limiter` được gọi **0** lần ngoài chính
`client.py`. Nhưng `TokenBucketRateLimiter` **đang chạy thật** ở
`async_client.py:90` với `Config.RATE_LIMIT_RPM`. Vì vậy **không xoá gì ở W3.3**;
xem §4.

### T4 — `logger` rò token thật ⟵ rủi ro cao nhất đợt này

Đo bằng cách chạy `redact_sensitive_data()` trên 10 chuỗi, kiểm tra JWT/OTP có
còn sót:

| Chuỗi đưa vào | Kết quả |
|:--|:--|
| `token=<JWT>` | ok |
| `"apiKey": "<JWT>"` | ok |
| `api_key=<JWT>` | ok |
| `x-api-key: <JWT>` | ok |
| `password: hunter2` | ok |
| `"access_token": "<JWT>"` | ok |
| **`Authorization: Bearer <JWT>`** | **RÒ — JWT nguyên văn** |
| **`str({'Authorization': 'Bearer <JWT>'})`** | **RÒ** |
| **`<JWT>` trần, không tên biến** | **RÒ** |
| **`otp 123456`** | **RÒ** |

⇒ **4/10 rò.** Nguyên nhân đo được: `SENSITIVE_PATTERN`
(`core/utils/logger.py:24-27`) bắt buộc có `<tên biến> [:=] <giá trị>`, và lớp ký
tự giá trị là `[^"\',\s}]+` — **dừng ở dấu cách** ⇒ `Authorization: Bearer <JWT>`
chỉ ăn `Bearer`, JWT đứng sau lọt.

**Phạm vi thật (đính chính sau audit #7 — bản v1 nói quá):**

| File | Có dùng logger này? |
|:--|:--|
| `connector/dnse/trade.py:9,12` (`get_logger`) | ✅ **Có** — đây là lane đặt lệnh |
| `explorer/tcbs/auth.py` | ❌ **Không có logger** (106 dòng, đọc token từ env rồi không log) |
| `broker/ssi/auth.py:35` | ❌ Dùng `logging.getLogger` chuẩn — `SensitiveDataFilter` chỉ gắn ở `logger.py:106` cho logger dựng bằng `get_logger`, **không** gắn root |

⇒ Vẫn là lỗi thật (đường đặt lệnh DNSE đi qua đây), nhưng **phạm vi hẹp hơn bản v1
nói**. Ghi đúng, không phóng to.

**Lỗi quá rộng đang sống (audit #17):** regex **không có word boundary**, nên
`redact_sensitive_data('monkey=abc')` → `'monkey: "***REDACTED***"'` — vì `key` là
tên nhạy cảm và khớp **ở giữa** từ khác. Đây là dạng **L-R07**: công cụ "bảo vệ"
bằng cách phá dữ liệu người dùng cần.

⚠ **Không** dùng `broker/security/redaction.py` làm chuẩn: đó là `Redactor` cho
dict/header, **không** bắt được chuỗi log tự do. Hai lớp khác nhau, cả hai đúng.

---

## 1.2 ĐÍNH CHÍNH VÒNG 2 — tôi đã dẫn đường dẫn người dùng sai

Bản v2 lập luận: *"`common.data.Quote.history` không có wrapper tenacity ⇒ 1 lệnh =
1 attempt"*. **Sai.** Tôi soi `hasattr(Quote.history, 'retry')` — đúng là `False` —
nhưng `@retry` **không** phải nơi retry xảy ra ở đường này.

Đo lại bằng call counter thật (`%TEMP%\opencode\recheck_attempts.py`):

| Đường | Lệnh | Attempt đo được | Exception |
|:--|:--|:--|:--|
| `common.data.Quote.history`, source **cố định** | `q.history()` | **3** | `ConnectionError` |
| `common.data.Quote.history`, **AUTO**, cả 2 provider trả 429 | `q2.history()` | **6** (= 3 × 2 provider) | `ConnectionError` |

Nguyên nhân: `common/data.py:647-656` (đường cố định) và `common/data.py:665-674`
(đường AUTO) dựng `Retrying(stop=stop_after_attempt(3),
retry=retry_if_exception_type((RequestException, ConnectionError, TimeoutError)))`
**bên trong** `_run_with_failover` — không phải decorator. Docstring ở
`common/data.py:722-730` nói rõ điều này ("Method này KHÔNG có decorator `@retry`").

⚠ **`common/data.py` KHÔNG có `Config.DEFAULT_RETRIES`.** Nó dùng
`Config` **cục bộ** định nghĩa tại `common/data.py:197-203`. Đây là **nguồn sự
thật thứ hai** cho cùng một khái niệm — cùng bệnh với "2 bản chuẩn hoá" của Wave 2.
Sửa trong lát này **không** gộp 2 `Config` (ngoài phạm vi); chỉ dùng đúng class mà
`data.py` đang dùng.

⇒ **Blocker vòng 2:** AC-3.2/AC-3.4 của bản v2 **không thi hành được**, vì lát W3
chưa sờ tới `common/data.py` — file mang **đường người dùng thật**.

⇒ **Sửa:** `common/data.py` **vào** lát W3 (chỉ sửa `_run_with_failover`), và AC
đo lại trên chính đường đó.

### 1.3 Lỗi sống thứ ba: `SensitiveDataFilter` **phá** `record.args`

Đo (`%TEMP%\opencode\probe_args.py`), `log.info("x=%s", dict)`:

| Đầu vào | Kết quả @ `4cd0f2d` |
|:--|:--|
| `log.info("x=%s", {"a": 1, "b": 2})` | **`TypeError: not all arguments converted during string formatting`** ⇒ **mất trọn dòng log**, in traceback |
| `log.info("x=%s", {"Authorization": "Bearer <JWT>"})` | in ra `x=Authorization` — giá trị (JWT) biến mất, dòng log **bị bóp méo** |
| `log.info("n=%d", 42)` | `n=42` — đúng |

Nguyên nhân: Python 3.13 `LogRecord.__init__` bóc `args=({...},)` thành **chính
dict**; filter tại `logger.py:51` duyệt nó như một iterable nên ra **key**.

⚠ Hệ quả ngược lại với trực giác: ở ca 1 kia JWT **không** lọt (vì giá trị bị mất
trước khi format). Nhưng nếu chỉ vá regex mà **không** sửa filter thì
`getMessage()` sẽ trả lại **giá trị thật** trong dict ⇒ **mở lại** đường rò.
⇒ T4.3 **bắt buộc** phải sửa filter, không được chỉ thêm regex.

---

## 2. AC — đo đúng thứ người dùng quan tâm (hazard 8)

> *Nếu AC pass nhưng tính năng vẫn vô dụng, AC có bắt được không?*

⚠ **Đường đo: `common.data.Quote`** — đường người dùng thật qua
`Vnbroker().stock('TCB').quote` (`StockComponents` dựng `Quote` tại
`common/data.py:413`; xác nhận bằng `sys.settrace`: đỉnh stack là
`common/data.py:719 history` → `common/data.py:607 _run_with_failover`).

| AC | Given/When/Then | Chống proxy |
|:--|:--|:--|
| **AC-3.1** | **Ở chế độ AUTO**: server trả `429` + `Retry-After: 120` ⇒ `cooldown_remaining_sec` của provider đó **≥ 120** | Không chấp nhận "cooldown > 0". ⚠ **chỉ trong AUTO**: `base.py:163-164` source cố định thì `raise` thẳng, `record_failure` không chạy. ⚠ `data.py:696,709` gọi `record_failure` **2 đối số** ⇒ phải sửa mới truyền được `retry_after` |
| **AC-3.2** | Source **cố định** trả 429 ⇒ **đúng 1** attempt cho một `history()` | **ĐỎ trên `4cd0f2d`: đo được 3** (`recheck_attempts.py`). Đếm bằng call counter |
| **AC-3.3** | **AUTO**, cả 2 provider trả 429 ⇒ **đúng 2** attempt (1/provider), không phải 6 | **ĐỎ trên `4cd0f2d`: đo được 6** |
| **AC-3.4** | Provider A trả 429, B trả dữ liệu ⇒ `source_used == "B"` **và** A có `failures ≥ 1` | ⚠ **đã XANH ở `4cd0f2d`** ⇒ đây là AC hồi quy (regression), **không** phải bằng chứng fix. Giữ để chặn W3.0 **không** làm hỏng failover |
| **AC-3.5** | `should_failover(RateLimitError('kbs', retry_after=120))` == **`True`** | **ĐỎ trên `4cd0f2d` (đo `False`)** — canh gác trực tiếp blocker #15 |
| **AC-4.1** | 10 chuỗi ở bảng T4 ⇒ **0** JWT/OTP còn sót | **ĐỎ ở `4cd0f2d`: 4/10 rò** |
| **AC-4.2** | `price=12345`, `symbol=TCB`, `volume=1.2M`, `the user name is bob`, `key note: read the file` ⇒ **không** đổi | Chặn cách sửa phá huỷ (L-R07) |
| **AC-4.3** | `monkey=abc` ⇒ **không** đổi | **ĐỎ ở `4cd0f2d`** (lỗi quá rộng đang sống) |
| **AC-4.4** | `log.info("x=%s", {"a":1,"b":2})` ⇒ **không** `TypeError`, dòng log **không mất** | **ĐỎ ở `4cd0f2d`** (đo `TypeError`) |
| **AC-4.5** | `log.info("x=%s", {"Authorization": "Bearer <JWT>"})` ⇒ JWT **không** lọt **và** dòng log đọc được | Chặn "vá regex làm mở lại đường rò" — cặp với §1.3 |

**Ràng buộc chống tự lừa (hazard 10):** mỗi test mới phải **ĐỎ trên `4cd0f2d`**.
Cách làm: `git show 4cd0f2d:<file> > <file>` → chạy → khôi phục.
**Không** dùng `git checkout --` (hazard 11).

⚠ **AC-3.4 đã xanh sẵn ở base** — nó là **canh gác hồi quy**, không phải bằng
chứng rằng W3.0 sửa được gì. Báo cáo phải ghi đúng phân loại này, không gộp
chung thành "AC xanh ⇒ fix có hiệu lực".

---

## 3. CHIA LÁT — file KHÔNG giao nhau (Stage 0.5)

Hai worktree, hai branch, từ `refs/heads/main` (dùng ref đầy đủ: repo có branch
`main` và remote-tracking `main` nên `main` trần bị ambiguous).

| Lát | Worktree / branch | File sẽ sửa | File sẽ tạo |
|:--|:--|:--|:--|
| **W3** rate-limit | `../vnbroker-w34-ratelimit` / `feat/w34-ratelimit` | `core/exceptions.py`, `core/utils/client.py`, `core/source_router.py`, `base.py`, **`common/data.py`** (chỉ `_run_with_failover`) | `tests/unit/core/test_rate_limit_cooldown.py` |
| **T4** logger | `../vnbroker-w34-logger` / `feat/w34-logger` | `vnbroker/core/utils/logger.py` | `tests/unit/core/test_logger_redaction.py` |

**Kiểm tra giao nhau:** không có cặp file nào trùng. `W3` **không** đụng
`logger.py`; `T4` **không** đụng router. ✔

⚠ **`common/data.py` (1823L) vào lát W3 là bắt buộc** (audit vòng 2, blocker #1):
đó là đường người dùng thật, và nó **tự** retry 429. Không sửa nó thì AC-3.2/3.3
không bao giờ xanh. Chỉ đụng `_run_with_failover` — **không** tách file, **không**
gộp 2 class `Config` (nợ N9).

⚠ **`common/data.py` vốn đã vượt ngân sách 800L** (1823 dòng). Lát này **không**
làm nó lớn thêm: chỉ sửa trong `_run_with_failover`, và số dòng phải **không tăng**
(kiểm bằng lệnh ở §0.1 trước/sau).

⚠ **`.venv` / `.env` không tự có trong worktree** (L-P01). Baseline phải đo **tại
worktree**, không ép số của main tree. Cổng chạy được ở cả hai nơi bằng junction:
```powershell
cmd /c mklink /J ..\vnbroker-w34-ratelimit\.venv .venv
```
⚠ **Gỡ junction TRƯỚC khi xoá worktree**, không `/s` (L-P02 / hazard 21).

### 3.1 Những file **KHÔNG** ai được chạm (deny list)

`docs/CLAIMS.md` · `docs/CHANGELOG.md` · `CLAUDE.md` · `pyproject.toml` ·
`scripts/check_all.ps1` · `scripts/check_provider_consistency.py` ·
`.gitattributes` — **chỉ coordinator** (tôi) được commit trong đợt này.

---

## 4. WAVE 3 — Rate-limit thật

Thứ tự **bắt buộc**: W3.0 (sửa class) **trước** W3.1. Làm ngược thứ tự sẽ tạo ra
đúng blocker mà audit vừa bắt.

| Việc | Nội dung | File |
|:--|:--|:--|
| **W3.0** | `RateLimitError(NetworkError, ConnectionError)` + thuộc tính `retry_after: float \| None` (hiện chỉ có `details["retry_after"]`) | `core/exceptions.py` |
| **W3.1** | `send_request_direct` đọc **`Retry-After`** từ `response.headers`; khi status là 429 thì `raise RateLimitError(..., retry_after=…)` **thay cho** `ConnectionError` | `core/utils/client.py` |
| **W3.2** | `record_failure` nhận `retry_after: float \| None = None`; cooldown = **max**(suy đoán, `retry_after`), kẹp trong `[1, RETRY_AFTER_MAX_SECONDS]` | `core/source_router.py` |
| **W3.3** | `base.py::history` đổi `retry=` sang `retry_if_not_exception_type(RateLimitError)` ⇒ 429 **không** retry | `base.py` |
| **W3.4** | `base.py::_call_provider_method` bắt `RateLimitError` → `record_failure(..., retry_after=…)` rồi **chuyển provider ngay** | `base.py` |
| **W3.5** | `RETRY_AFTER_MAX_SECONDS` trong `vnbroker/config.py::Config` (**chưa tồn tại**) | `config.py` |
| **W3.6** | ⚠ **`common/data.py::_run_with_failover`** — đường người dùng thật: `retry_if_not_exception_type(RateLimitError)` ở **cả hai** `Retrying` (`:647-656` và `:665-674`), và truyền `retry_after` vào `record_failure` ở `:696` và `:709` | `common/data.py` |

⚠ **Chỉ `Retry-After`.** Bản v1 viết `X-RateLimit-*`; audit vòng 2 bác bỏ: đo
`git grep -n 'X-RateLimit' 4cd0f2d` → **0** kết quả, và chính khảo sát của repo
(`REPORT_TIER1_EXPLORER_SURVEY.md:164`) ghi *"Đọc header `X-RateLimit-*` | **0** |
Không provider nào công bố giới hạn"*. **Đọc header không tồn tại là bịa đặc tả.**
Chỉ `Retry-After` — đây là header **duy nhất** RFC 9110 §10.2.4 quy định, và
`Retry-After: <số giây>` là dạng phổ biến; **không** cài HTTP-date parser (cần
`email.utils.parsedate_to_datetime`, và không provider nào trong repo gửi dạng
đó — nợ N10). Giá trị không parse được ⇒ coi như **không có** ⇒ rơi về hành vi
suy đoán cũ.

⚠ **Sửa `ConnectionError` cũ thành `RateLimitError` là thay đổi exception type
người dùng thấy.** Breaking change ⇒ phải ghi vào `VERSION_NOTICES` (`config.py:78`).
Bù lại: class mới **vẫn** `isinstance(..., ConnectionError)` (kiểm chứng MRO ở
§1.1) nên code bắt `except ConnectionError` của người dùng **không** hỏng.

### W3.3 — token-bucket: **không** xoá, và **vì sao**

Đo đã đảo ngược kết luận của tài liệu cũ (L-E01):
- `configure_rate_limiter()` — gọi **0** lần ⇒ đường token-bucket sync là **opt-in
  và mặc định tắt**. Đây là **thiết kế có chủ ý** (dòng 26 ghi rõ), không phải
  code chết.
- `TokenBucketRateLimiter` — **đang chạy thật** ở `async_client.py:90`.

⇒ **Không** xoá 33 lượt nhắc test. Xoá chúng là mất coverage của một thứ đang
chạy, để "dọn" một cái tên không ai gọi.

### Chốt thiết kế trước khi giao (L-P03 / L-P06)

- `RateLimitError` **đã có sẵn** ở `core/exceptions.py:292` ⇒ dùng lại, sửa kế
  thừa, **không** viết bản thứ hai (tránh lặp lại đúng lỗi "2 bản chuẩn hoá"
  của Wave 2).
- **Không** sửa `should_failover` — sửa kế thừa của class nhỏ hơn và không đổi
  hợp đồng của hàm (đã kiểm chứng: `should_failover=True` sau khi thêm
  `ConnectionError`).
- `base.py` sửa `history()`; **36** decorator kia trong `api/*.py` **không** nằm
  trong phạm vi (N1). Ghi nợ rõ, không im lặng bỏ.

---

## 5. WAVE 4 — Logger không rò token

| Việc | Nội dung |
|:--|:--|
| **T4.1** | `Bearer <token>` — scheme + **khoảng trắng** + token |
| **T4.2** | JWT trần: `\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b` — redact **ở bất kỳ đâu**, không cần tên biến |
| **T4.3** | ⚠ **`SensitiveDataFilter` phá `record.args`** (đo ở §1.3): dict 2 khóa ⇒ `TypeError` ⇒ **mất dòng log**; dict 1 khóa ⇒ in ra **key** thay vì giá trị. Sửa: chỉ duyệt `args` khi nó **không phải** dict/bytes; nếu là dict thì redact **giá trị** qua `Redactor`-style, **không** `str()` hoá (sẽ phá `%d`/`%r` — audit #20) |
| **T4.4** | OTP trần: `(?<![\w])(?:otp\|otp_code\|mfa\|totp\|pin\|pin_code\|passcode)[\s:=]+(\d{4,8})(?![\d])` — **neo chữ số** để không ăn prose |
| **T4.5** | **Word boundary** cho mọi tên biến: `(?<![A-Za-z0-9_])key(?![A-Za-z0-9_])`. Không có nó thì `monkey=abc` bị redact — lỗi quá rộng **đang sống** |

⚠ **Thứ tự áp dụng:** `Bearer` → `JWT trần` → `OTP neo chữ số` → `key: value`.
Với JWT thật (`eyJ…`) thì **thứ tự không đổi kết quả** (đo: `leak in wrong
order: False`) — nhưng vẫn giữ thứ tự này vì nó là thứ tự **ràng buộc** cho mọi
token **không** bắt đầu bằng `eyJ`. Không tuyên bố "thứ tự là bắt buộc với JWT".

⚠ **L-R07 — cấm tuyệt đối:** không thêm `pin`/`price` vào danh sách gợi ý; không
cho phép dấu cách làm dấu phân cách chung (đo: phá `"the user name is bob"`).
Không thay đổi nào ở lát này được làm **mất** dữ liệu người dùng cần.

---

## 6. NGOÀI PHẠM VI (non-goals) — nêu thẳng để audit không tìm nhầm

- ❌ `vnbroker/broker/**` (lane tiền thật) — T4 **không** sửa `broker/security/`.
- ❌ 36 decorator `@retry` thiếu `reraise` trong `api/*.py` — **nợ N1**.
- ❌ T1 (10 file >800L trong `vnbroker/`), T3 (mypy 1138), T2 (13 lỗi ruff tests),
  A3 (screener 0 dòng) — Owner **không** chọn trong đợt này.
- ❌ Không gọi write endpoint. Không in giá trị credential.
- ❌ Không đổi thứ tự AUTO (W-2) — cần benchmark, chưa đo.

### 6.1 `vnbroker/api/quote.py` — chưa có chủ (audit #18)

File này **không** thuộc lát nào, **không** nằm trong deny list, nhưng lại nằm
trên đường mà AC-3.2/AC-3.4 từng viết. Sau khi sửa AC sang `common.data.Quote`
thì **không còn gì chạm tới nó** — nhưng phải ghi tên rõ để lát sau không tưởng
đã ai phủ.

**Chốt:** lát W3 **không** sửa `api/quote.py`; nợ N1 đã ghi.

---

## 7. NỢ GHI RÕ — không làm trong đợt này

| # | Nợ | Vì sao | Số đo |
|:--|:--|:--|:--|
| **N1** | 36/40 `@retry` trong `api/*.py` không `reraise=True` **và không có `retry=`** ⇒ retry mọi exception, người dùng nhận `RetryError` | ngoài phạm vi; sửa 36 chỗ đổi hành vi lỗi cho **mọi** module | script AST, §1 W3.2 |
| **N2** | T1 — 10 file >800L trong `vnbroker/` (`common/data.py` 1823L) | Owner không chọn | §0.1 |
| **N3** | T2 — 13 lỗi `ruff check tests` | Owner không chọn | baseline §0 |
| **N4** | T3 — mypy 1138 lỗi | Owner không chọn | baseline §0 |
| **N5** | A3 — screener VCI/KBS trả 0 dòng | Owner không chọn | — |
| **N6** | A2 — benchmark để quyết thứ tự AUTO | Owner chọn "đo rồi mới quyết" nhưng **chưa** có số đo p99 | — |
| **N7** | A1 — `.env` tự nạp (Owner chọn hướng **opt-in qua env flag**) | cần `python-dotenv` hoặc bộ đọc tay — thêm phụ thuộc là quyết định riêng | — |
| **N8** | B1 — loại `intraday` của TCBS khỏi AUTO (Owner **đã chọn**, chưa làm ở đợt này) | `ProviderPool.AUTH_PROVIDERS['tcbs']['supports']` là danh sách **module**, còn `intraday` là **method** ⇒ cần bảng loại theo method + quy tắc C6 mới trong `check_provider_consistency.py` | `provider_pool.py:46` |
| **N9** | `common/data.py:197-203` định nghĩa class `Config` **thứ hai**, có `DEFAULT_RETRIES = 3` — trùng khái niệm với `vnbroker/config.py` | gộp 2 class là refactor riêng; lát này chỉ dùng đúng class `data.py` đang dùng | `python -c "from vnbroker.config import Config; print(hasattr(Config,'DEFAULT_RETRIES'))"` → `False` |
| **N10** | `Retry-After` dạng **HTTP-date** chưa xử lý | không provider nào trong repo gửi dạng đó; thêm parser là bịa nhu cầu. Giá trị không parse ⇒ coi như không có | `git grep -n 'X-RateLimit' 4cd0f2d` → 0 |
| **N11** | `explorer/dnse/quote.py:139-140` `_raise_for_failover` viết lại mọi `ConnectionError` thành `ConnectionError` thuần, **mất** `retry_after` | tiền đề đủ để ghi nợ; DNSE hiện **không** đi qua `send_request_direct` nên chưa kích hoạt | `explorer/dnse/quote.py:139` |
| **N12** | `README.md` bị `check_version_sync.py` gate nhưng không thuộc lát nào | bump version sẽ kéo `README.md` + `pyproject.toml` + `CLAUDE.md`; cả ba là việc coordinator | `scripts/check_version_sync.py` |

---

## 8. ĐỊNH NGHĨA XONG

Wave 3+4 xong khi **đồng thời**:

1. **AC-3.1 … AC-3.5** và **AC-4.1 … AC-4.5** xanh. *(bản v2 loại sót AC-3.5 và
   AC-4.4 khỏi DoD — audit vòng 2, major #3.)*
2. **AC-3.2, AC-3.3, AC-3.5, AC-4.1, AC-4.3, AC-4.4** có bằng chứng **ĐỎ trên
   `4cd0f2d`** dán vào `docs/TEST_REPORT_TIER1_WAVE34.md` (lệnh + output thật).
   **AC-3.4 ghi rõ là hồi quy, xanh sẵn ở base** — không được tính là bằng chứng
   fix có hiệu lực.
3. `pwsh -File scripts/check_all.ps1` (không `-Quick`) **exit 0**.
4. Audit Stage 5: **0 blocker + 0 major**, `confidence: high`.
5. `common/data.py` **không dài thêm** (1823 dòng trước → ≤1823 sau).
6. Mọi con số trong báo cáo **có lệnh tái lập**.

**Rollback:** mỗi lát = **một** commit trên branch riêng ⇒ `git revert <sha>`.