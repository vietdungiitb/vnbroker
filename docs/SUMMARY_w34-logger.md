# SUMMARY — Wave 4 / lát T4: logger không rò token

**Worktree:** `C:\Mujoco Projects\vnbroker-w34-logger` · **branch:** `feat/w34-logger`
**Base:** `4cd0f2d` · **HEAD:** xem bảng commit dưới
**Plan:** `docs/PLAN_TIER1_WAVE34.md` §1 (T4), §1.3, §2 (AC-4.1…AC-4.5), §5
**Lessons áp dụng:** [L-R07, L-E01, L-E03, L-E04, L-E06, L-E07, L-P01, L-P03, L-P04, L-P06]
**Ngày đo:** 2026-10-10 · máy này · Python 3.13.14 · `C:\Mujoco Projects\vnbroker\.venv`

---

## 1. Commit

| # | SHA | Nội dung |
|:--|:--|:--|
| 1 | `a1b6fc9` | `test(logger): them test redaction cho logger.py (AC-4.1..AC-4.5)` |
| 2 | `78f163f` | `fix(logger): bat 4 duong ro token va pha record.args` |
| 3 | `048be6a` | `fix(logger): them type annotation de giu check_mypy_baseline.py xanh` |

Cả 3 viết message ra FILE rồi `git commit -F <file>` (`%TEMP%\opencode\w34\c1.txt` … `c3.txt`).

Rollback: `git revert 048be6a 78f163f a1b6fc9` trên branch này, hoặc
`git checkout feat/w34-logger` vì lát nằm trên 1 branch riêng.

## 2. File đổi

| File | +/- | Dòng |
|:--|:--|:--|
| `vnbroker/core/utils/logger.py` | +159 / −21 | 122 → 224 (dưới ngân sách 800L) |
| `tests/unit/core/test_logger_redaction.py` | +255 | **MỚI**, 182 dòng, 33 test |
| `docs/SUMMARY_w34-logger.md` | — | file này |

`git diff --stat 4cd0f2d..HEAD` (trước commit summary):
`tests/unit/core/test_logger_redaction.py | 255 +++`, `vnbroker/core/utils/logger.py | 159 ++++--`.

**Không chạm** (đúng phạm vi giao): `vnbroker/broker/**`, `vnbroker/broker/security/redaction.py`,
`vnbroker/core/utils/client.py`, `vnbroker/core/source_router.py`, `vnbroker/common/data.py`,
`docs/LESSONS/**`, `docs/CLAIMS.md`, `pyproject.toml`, `scripts/**`, `CLAUDE.md`, `.gitattributes`.

## 3. GATE — kèm output thật

Tất cả chạy **trong worktree này**, trên `feat/w34-logger`.

### 3.1 Test của lát

```
$ python -m pytest tests/unit/core/test_logger_redaction.py -q
33 passed in 3.53s
```

### 3.2 `tests/unit` + `tests/contract`

| | Lệnh | Kết quả |
|:--|:--|:--|
| **CŨA TÔI** | `pytest tests/unit tests/contract -q --ignore=tests/unit/core/test_logger_redaction.py` (logger.py = bản `4cd0f2d`) | `= 1881 passed, 6 skipped, 2 warnings, 3 subtests passed in 128.90s (0:02:08) =` |
| **SAU** | `pytest tests/unit tests/contract -q` | `= 1914 passed, 6 skipped, 2 warnings, 3 subtests passed in 150.33s (0:02:30) =` |

Chênh lệch **+33 passed, +0 failed** = đúng số test mới. **0 failure mới.**
Cả hai lần chạy trên cùng máy, cùng lần chạy (L-E07).

### 3.3 `pytest tests/contract` (đúng tham số gate của `check_all.ps1`)

```
$ python -m pytest tests/contract -q -p no:cacheprovider
91 passed in 55.06s
```

### 3.4 `ruff`

```
$ python -m ruff check vnbroker scripts tests/unit tests/contract
All checks passed!                                                        exit=0
$ python -m ruff check tests
Found 13 errors.                                                          exit=1   <- KNOWN-RED có sẵn ở HEAD
$ python -m ruff check tests | Select-String test_logger_redaction
(không có dòng nào)   <- file mới của tôi KHÔNG nằm trong 13 lỗi đó
```

### 3.5 `check_mypy_baseline.py`

Đỏ lần đầu, xanh lần sau — cả hai đều dán ở đây:

```
$ python scripts/check_mypy_baseline.py          <- SAU commit 78f163f
FAIL: 9 NEW mypy --strict errors (baseline 1266, now 1147, fixed 128):
  + vnbroker/core/utils/logger.py :: Call to untyped function "_redact_args" in typed context [no-untyped-call]
  + vnbroker/core/utils/logger.py :: Call to untyped function "_redact_embedded" in typed context [no-untyped-call]  (x5)
  + vnbroker/core/utils/logger.py :: Function is missing a type annotation [no-untyped-def]  (x3)
exit=1

$ python scripts/check_mypy_baseline.py          <- SAU commit 048be6a
OK: no new strict errors (baseline 1266, now 1138, fixed 128).
Note: run with --update to shrink the baseline.
exit=0
```

### 3.6 Full suite

```
$ python -m pytest tests/ -q --timeout=300            <- SAU
= 1 failed, 2006 passed, 30 skipped, 2 warnings, 3 subtests passed in 149.28s (0:02:29) =
FAILED tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible
       - AssertionError: khong thay DNSE_API_SECRET trong moi truong

$ python -m pytest tests/ -q --timeout=300 --ignore=tests/unit/core/test_logger_redaction.py   <- BASE 4cd0f2d
= 1 failed, 1973 passed, 30 skipped, 2 warnings, 3 subtests passed in 152.96s (0:02:32) =
FAILED tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible
```

**Failure đó có sẵn ở base, không phải do lát này.** Nguyên nhân: worktree không có `.env`
(L-P01) ⇒ `os.getenv("DNSE_API_SECRET")` rỗng. Chạy lại lần 2 một mình (L-E04):
vẫn đỏ, cùng assertion ⇒ không phải flake. Chênh lệch **+33 passed, +0 failed**.

> ⚠ pytest in thêm `PermissionError: [WinError 5] ... pytest-current` ở `atexit` **kể cả khi
> suite xanh**. `check_all.ps1:205-210` đã ghi rõ đây là thông tin nhiễu, không phải gate đỏ.
> Tôi đọc dòng kết quả thật (`= ... passed ... in ...s =`), không đọc dòng cuối.

### 3.7 Các gate còn lại của `check_all.ps1` (chạy tay, xem §6 về vì sao không gọi script)

| Gate | exit | Dòng kết quả thật |
|:--|:--:|:--|
| `version-sync` | 0 | `version-sync OK: 3.6.0 (pyproject, README, CLAUDE.md, config.py, tests/)` |
| `lessons` | 0 | `check_lessons: 5 file \| 24/40 lesson \| broker-risk.md 120d/7bai · evidence.md 120d/7bai · gate-integrity.md 75d/4bai · process.md 104d/6bai - sach.` |
| `lessons --self-test` | 0 | `check_lessons SELF-TEST PASS: 9 case theo dac ta.` |
| `tcbs-coverage` | 0 | `verify_tcbs_coverage: 48 path · 39 da noi · 9 chua noi` |
| `tcbs-bodies` | 0 | `check_tcbs_bodies: lech da biet (baseline): 0` |
| `tcbs-bodies --self-test` | 0 | `check_tcbs_bodies SELF-TEST PASS: 10 case theo dac ta.` |
| `provider-consistency` | 0 | `OK: khong co vi pham nao.` |
| `provider-consistency --self-test` | 0 | `self-test OK` |
| `mypy-raw` (`mypy vnbroker`) | 1 | 1138 lỗi — **KNOWN-RED**, không phải gate (`CLAUDE.md` nói rõ `--strict` là no-op) |

### 3.8 `pwsh -File scripts/check_all.ps1` — **CHƯA CHẠY**

```
$ pwsh -NoProfile -File scripts/check_all.ps1
[FATAL] Khong tim thay C:\Mujoco Projects\vnbroker-w34-logger\.venv\Scripts\python.exe
        Gate phai chay tren interpreter cua repo. Cai dat:
        python -m venv .venv
        .venv\Scripts\pip install -e ".[test,lint]"
exit=2
```

**Lý do:** worktree không có `.venv` (L-P01). Tôi **cố tình không** tạo junction
`mklink /J .venv`, vì L-P02: junction nằm trong cây sẽ bị `Remove-Item -Recurse` /
`rmdir /s` xuyên qua và **xoá `.venv` chính của main tree**. Việc đó là quyết định của
coordinator, không phải của tôi. Thay vào đó tôi chạy **từng gate thành phần** (§3.7) bằng
đúng interpreter main — bằng chứng tương đương, không tạo nguy hiểm.

**Cần coordinator chạy trước khi merge (DoD §8 mục 3):**
```powershell
cmd /c mklink /J ..\vnbroker-w34-logger\.venv .venv     # gỡ junction BẰNG `rmdir`, KHÔNG `/s`, trước khi xoá worktree
pwsh -File scripts/check_all.ps1                          # kỳ vọng: 9 PASS · 1 KNOWN-RED · exit 0
```
⚠ Dự kiến `pytest-full` **exit 1** vì `test_the_env_is_actually_visible` đỏ sẵn ở base
(không có `.env` trong worktree) — cần báo rõ đây là KNOWN-RED mới, **không** phải hồi quy.
Kịch bản đúng hơn: merge vào main rồi chạy gate ở main (có `.env`).

## 4. FAIL-BEFORE / PASS-AFTER

Cách làm (không dùng `git checkout --` — hazard 11):
```powershell
git -C <worktree> show 4cd0f2d:vnbroker/core/utils/logger.py > $env:TEMP\opencode\w34\logger.ORIG.py
cmd /c copy /y ...\logger.ORIG.py ...\vnbroker\core\utils\logger.py
# kiểm tra byte-exact TRƯỚC khi chạy (L-E03):
git hash-object --no-filters logger.ORIG.py   ->  81ef5825b114deafe117e83b62637bc5cf456bdf
git rev-parse 4cd0f2d:vnbroker/core/utils/logger.py  ->  81ef5825b114deafe117e83b62637bc5cf456bdf
```

**Trước (bản `4cd0f2d`) — output nguyên văn:**
```
======================== 11 failed, 22 passed in 2.92s ========================
FAILED ...test_ac_4_1_no_credential_survives_redaction[Authorization-Bearer] - AssertionError: JWT survived redaction of 'Authorization: Bearer eyJ...' -> 'Authorization: "***REDACTED***" eyJ...'
FAILED ...test_ac_4_1_no_credential_survives_redaction[repr-dict]           - AssertionError: JWT survived redaction of "{'Authorization': 'Bearer eyJ...'}" -> "{'Authorization': "***REDACTED***" eyJ...'}"
FAILED ...test_ac_4_1_no_credential_survives_redaction[bare-JWT-no-key]     - AssertionError: JWT survived redaction of 'eyJ...' -> 'eyJ...'
FAILED ...test_ac_4_1_no_credential_survives_redaction[otp-space-separated]  - AssertionError: OTP survived redaction of 'otp 123456' -> 'otp 123456'
FAILED ...test_ac_4_3_monkey_is_not_treated_as_key - assert 'monkey: "***REDACTED***"' == 'monkey=abc'
FAILED ...test_ac_4_4_dict_argument_does_not_destroy_the_log_line - AssertionError: log line was lost entirely
FAILED ...test_ac_4_5_dict_argument_authorization_is_redacted_and_readable - AssertionError: assert 'REDACTED' in 'x=Authorization\n'
FAILED ...test_string_argument_is_redacted - AssertionError: assert 'eyJ...' not in 'auth header: Bearer eyJ...\n'
FAILED ...test_bytes_argument_with_jwt_is_redacted - assert 'eyJ...' not in "payload=b'Bearer eyJ...'\n"
FAILED ...test_jwt_ending_in_base64url_dash_is_still_redacted - assert 'eyJ...ssw5-' not in 'raw=eyJ...ssw5-'
FAILED ...test_redaction_through_a_real_handler_leaves_text_alone[monkey=abc] - assert 'monkey: "***REDACTED***"' == 'monkey=abc'
```

**Sau:**
```
============================= 33 passed in 3.53s =============================
```

### 4.1 AC map

| AC | Test | Base | Sau |
|:--|:--|:--|:--|
| **AC-4.1** | `test_ac_4_1_no_credential_survives_redaction` (10 case) | ĐỎ 4/10 | XANH 10/10 |
| **AC-4.2** | `test_ac_4_2_ordinary_log_text_is_untouched` (5 case) | XANH (canh gác chống phá dữ liệu) | XANH |
| **AC-4.3** | `test_ac_4_3_monkey_is_not_treated_as_key` | ĐỎ | XANH |
| **AC-4.4** | `test_ac_4_4_dict_argument_does_not_destroy_the_log_line` | ĐỎ (dòng log rỗng) | XANH |
| **AC-4.5** | `test_ac_4_5_dict_argument_authorization_is_redacted_and_readable` | ĐỎ (`x=Authorization`) | XANH |

⚠ **AC-4.2 xanh ở base ⇒ là canh gác hồi quy, KHÔNG phải bằng chứng fix có hiệu lực.**
Bằng chứng fix nằm ở AC-4.1 (4→0), AC-4.3, AC-4.4, AC-4.5.

### 4.2 Đo lại bằng probe độc lập (`%TEMP%\opencode\w34\probe_base.py`)

Cùng một script, chạy trước và sau:

| Bảng | Base `4cd0f2d` | Sau |
|:--|:--|:--|
| Rò token trong 10 chuỗi | `LEAKS = 4/10` | **`LEAKS = 0/10`** |
| Văn bản thường bị bóp méo | `MANGLED = 1/6` (`monkey=abc`) | **`MANGLED = 0/6`** |
| `log.info("x=%s", {"a":1,"b":2})` | `status: OK` nhưng **`output: ''`** + `TypeError: not all arguments converted during string formatting` trên stderr | **`output: "x={'a': 1, 'b': 2}"`** |
| `log.info("x=%s", {"Authorization": "Bearer <JWT>"})` | `output: 'x=Authorization'` | **`output: "x={'Authorization': 'Bearer ***REDACTED***'}"`** |
| `log.info("n=%d", 42)` | `output: 'n=42'` | `output: 'n=42'` (không hồi quy) |

Traceback `TypeError` gốc, in ra ngoài pytest ở base (verbatim từ `probe_base.py`):
```
TypeError: not all arguments converted during string formatting
Call stack:
  File "...\Lib\logging\__init__.py", line 400, in getMessage
    msg = msg % self.args
Message: 'x=%s'
Arguments: ('a', 'b')
```
`Arguments: ('a', 'b')` **chính là bằng chứng** cho §1.3 của plan: filter đã biến dict thành
tuple **key** trước khi format.

## 5. Thiết kế — vì sao KHÔNG dùng dấu cách làm dấu phân cách

Đây là bẫy chính của lát (L-R07). Đo lại trên bản regex v1 của plan:
```
'the user name is bob'      ->  'the user: "***REDACTED***" is bob'
'key note: read the file'   ->  'key: "***REDACTED***" read the file'
```
Vì `SENSITIVE_KEYS` chứa `user`, `key`, `auth`, `login`. **Không dùng.** Thay bằng:

| # | Rule | Vì sao |
|:--|:--|:--|
| 1 | `BEARER_PATTERN` = `(?<![A-Za-z0-9])Bearer[ \t]+[b64token charset]` | lớp giá trị cũ `[^"'\s,}]+` **dừng ở dấu cách** ⇒ chỉ ăn `Bearer`. Charset token lấy từ RFC 6750 nên không ăn dấu phay/ngoặc. Giữ lại chữ `Bearer` để log vẫn nói được "đây là auth dạng bearer" mà không lộ gì |
| 2 | `JWT_PATTERN` = `\beyJ…(?![A-Za-z0-9_-])` | bắt JWT **trần**, không cần tên biến. Đuôi là `(?![A-Za-z0-9_-])` **không phải** `\b`: JWT base64url được phép kết thúc bằng `-`/`_`, mà `\b` không phải biên ở đó ⇒ `\b` sẽ **bỏ sót**. Test riêng: `test_jwt_ending_in_base64url_dash_is_still_redacted` |
| 3 | `OTP_PATTERN` = `(?<!\w)(?:otp\|otp_code\|otpcode\|mfa\|totp\|pin\|pin_code\|pincode\|passcode)[\s:=]+(\d{4,8})(?![\d])` | **neo vào giá trị, không neo vào dấu phân cách**: phải là 4–8 chữ số, và `(?![\d])` chặn việc ăn nửa một số dài hơn. Các từ này nằm ở `OTP_PREFIXES`, **không** thêm vào `SENSITIVE_KEYS`, để chúng không kế thừa hành vi phân cách của rule 4 |
| 4 | `SENSITIVE_PATTERN` có `(?<![A-Za-z0-9_]) … (?![A-Za-z0-9_])` | `key` là tên nhạy cảm và **khớp ở giữa từ** ⇒ `monkey=abc` bị đổi thành `monkey: "***REDACTED***"`. Dấu gạch vẫn lọt qua được (`x-api-key` còn hoạt động) vì `-` không thuộc `[A-Za-z0-9_]`. Alternative xếp **theo độ dài giảm dần** để `secret` không thắng `apiSecret` tuỳ thứ tự lặp của set |

Thứ tự áp dụng cố định: **Bearer → JWT trần → OTP → key:value**. Với JWT thật thứ tự không
đổi kết quả; nó là hợp đồng cho credential **không** bắt đầu bằng `eyJ`. Ghi trong docstring.

### 5.1 T4.3 — vì sao **không** `str()` mọi arg

`str()` mọi arg sẽ phá `%d`/`%r` (`'42' %d` ⇒ `TypeError`) và phá kiểm tra số lượng arg của
`%-tuple` (`'x=%s' % ('a',)` OK nhưng `'x=%s %s' % ['a','b']` ⇒ lỗi) — tức **mất dòng log**,
đúng loại lỗi mà lát này phải chặn. Nên `_redact_args()` xử lý **theo kiểu dữ liệu**:

| Kiểu | Xử lý | Vì sao an toàn |
|:--|:--|:--|
| `tuple` / `list` | map từng phần tử, **giữ nguyên kiểu** | giữ nguyên số lượng arg mà `%` kiểm tra |
| `dict` | `{k: redact(v)}`, **giữ nguyên là dict** | `msg % dict` vẫn đúng, và giá trị (chỗ chứa JWT) vẫn được redact |
| `bytes`/`bytearray` | `decode(errors='surrogateescape')` → redact → `encode` ngược lại | round-trip **lossless** khi không đổi ⇒ byte không bị sửa thì giống hệt; khi redact thì chỉ đoạn ASCII bị thay |
| `str` | `redact_sensitive_data` | như cũ |
| còn lại (`int`, `float`, `Decimal`, `datetime`, …) | giữ nguyên | `%d`/`%r` không hỏng |

**Dict KEY không được redact** (chỉ value) — cố ý: redact key có thể làm hai key trùng nhau và
làm hỏng nghĩa. Ghi lại ở §7.

## 6. Sai lệch so với chỉ dẫn — nói thẳng

Chỉ dẫn yêu cầu *"giữ style file này (đang KHÔNG có type hint)"* **và** *"đừng tạo strict
error mới"*. Hai điều đó xung đột: `filter()` là hàm **duy nhất có type** trong file ⇒ mypy
coi thân nó là *typed context* ⇒ **mọi** lời gọi vào helper không chú kiểu đều là lỗi strict
**mới**. Đo được 9 lỗi (dán ở §3.5).

Tôi chọn **giữ gate xanh**: thêm đúng 3 chú kiểu trên 3 hàm mới
(`_redact_otp(match: "re.Match[str]") -> str`, `_redact_embedded(value: Any) -> Any`,
`_redact_args(args: Any) -> Any`) + `from typing import Any`. **Không** `# type: ignore`,
**không** `# noqa`, **không** đụng hàm cũ. Lý do ghi trong docstring `_redact_args`.
Nếu coordinator muốn giữ tuyệt đối "không type hint", thì phải chấp nhận gate đỏ 9 lỗi —
đó là quyết định của coordinator, không phải mặc định của tôi.

## 7. Rủi ro

| # | Rủi ro | Đánh giá |
|:--|:--|:--|
| R1 | `JWT_PATTERN` chỉ bắt JWT bắt đầu bằng `eyJ` (base64 của header `{"`). JWT ký bằng header không phải JSON sẽ không khớp | Chấp nhận. Anchor này là đánh đổi để **không** ăn base64 thường. Nợ nếu sau này cần |
| R2 | Rule OTP có thể ăn số trong câu tiếng Anh/việt kiểu `"pin 1234567"` ngoài ngữ cảnh đăng nhập | Hẹp (4–8 chữ số, sau đúng từ khóa, `(?<!\w)` chặn `spin`/`shipping`). Chọn an toàn hơn là rò |
| R3 | Log tiếng Việt kiểu `"mã pin của tôi là 123456"` **không** bị bắt (mọi pattern neo ASCII) | **Ngoài phạm vi**, ghi ở §8. Chưa có bằng chứng nào trong repo rằng log ghi OTP bằng tiếng Việt |
| R4 | Key của dict không được redact | Cố ý (§5.1). Nếu từng gặp credential làm **key** thì phải xử lý riêng |
| R5 | `record.msg` vẫn được redact như cũ, nên `log.info("apiKey=%s", v)` vẫn sinh `TypeError` | **Có sẵn từ trước**, không do lát này, và lát này **không làm nó nặng thêm** (word boundary làm rule 4 **hẹp hơn**, không rộng hơn). Xem §8 |
| R6 | `redact_sensitive_data` vẫn đổi `=` thành `:` trong cặp bị redact | Giữ nguyên hành vi cũ để giảm bán kính ảnh hưởng. Là thay đổi **thẩm mỹ**, không mất dữ liệu. Đáng mở ticket riêng |
| R7 | `logger.py` 122 → 224 dòng | Vẫn rất xa ngân sách 800L. Không tách file |

## 8. Ngoài phạm vi — những thứ tôi thấy nhưng KHÔNG sửa

1. **`log.info("apiKey=%s", value)` vẫn mất dòng log.** `record.msg` là *format string*; regex
   key:value ăn luôn `%s`, ra `apiKey: "***REDACTED***"%s`, rồi `msg % args` ⇒ lỗi số lượng arg.
   Đo được trên **bản gốc** (`api_key=%s` → `api_key: "***REDACTED***"`), nên **có sẵn**, không
   phải hồi quy. Chưa có AC nào phủ. Khắc phục đúng sẽ phải *không* redact format string khi
   nó còn `%`-spec — cần thêm AC và thêm test, nên tách lát riêng.
2. **`broker/ssi/auth.py` không đi qua `SensitiveDataFilter`.** Filter chỉ gắn cho logger dựng
   bằng `get_logger()` của `logger.py`; `broker/ssi/*` dùng `logging.getLogger` trực tiếp.
   Nghĩa là lane SSI **không** được redact. Ngoài phạm vi (broker lane), nhưng là rủi ro thật
   — nên ghi tên để lát sau không tưởng đã ai phủ.
3. **Chỉ `connector/dnse/trade.py` dùng logger này** (đường đặt lệnh). `explorer/tcbs/auth.py`
   không có logger. Phạm vi nhỏ hơn "toàn repo" — đã ghi đúng trong plan §1.
4. **`SENSITIVE_KEYS` không có `pin`/`passcode`** và tôi **không** thêm (L-R07: danh sách gợi ý
   phải không thể bị hành động sai). OTP dùng `OTP_PREFIXES` riêng.
5. **`redact_sensitive_data` trả về `str` cho mọi input**, kể cả bytes/dict khi gọi trực tiếp.
   Đường `record.args` không đi qua đó (dùng `_redact_embedded` giữ kiểu).
6. **Không có test nào cho `advanced_logger`/`get_logger`** (chọn handler, đặt level, xoá
   handler cũ). Tôi chỉ thêm test cho phần redaction — đúng phạm vi giao.
7. **Con số baseline của plan đã hơi cũ.** Plan §0 ghi `1978 passed, 26 skipped` cho
   `pytest tests/`; tôi đo ở **worktree này** ở `4cd0f2d`: `1973 passed, 30 skipped`. Chênh do
   môi trường (worktree không có `.env`) — đúng thứ L-E01/L-E07 cảnh báo.

## 9. Bài học quy trình rút ra

**a) Bẫy "sửa bằng cách phá" là bẫy mặc định của mọi lát bảo mật.** Cả hai cách sửa hiển nhiên
đều phá dữ liệu, và cả hai đều *trông* như đã thêm bảo mật:
`str()` mọi arg → `%d` vỡ → mất dòng log; cho phép dấu cách làm dấu phân cách → ăn prose.
Không có cách nào trong hai đó **làm tăng** an toàn dữ liệu. Cả hai đều phải bị loại *trước khi*
viết regex, không phải sau. Bài học vận hành: **AC phải có cả AC "dữ liệu thường phải ra
nguyên văn"** (AC-4.2), nếu không thì lát sau sẽ giao "thêm rule" và không ai đo hướng ngược.

**b) Bằng chứng ĐỎ phải chạm đúng tầng lỗi.** `test_ac_4_5` ở base đỏ vì dòng log bị bóp méo
(`x=Authorization`), **không** phải vì JWT lọt — ở base JWT *có* biến mất (vì giá trị bị mất
trước khi format). Nếu tôi chỉ assert "JWT không còn", test đó sẽ **xanh ở base** và tôi sẽ báo
PASS oan. Giữ cả hai vế trong một test là điều duy nhất làm AC-4.5 thành bằng chứng thật —
đây là L-E06 áp dụng cho bảo mật, không chỉ cho write path.

**c) `git show > file` trong PowerShell là nguồn bằng chứng hỏng âm thầm.** `>` của PowerShell 7
sai charset (mũi tên `→` trong file tôi đọc ra là `›`). Đã dùng `cmd /c` cho redirection rồi
**kiểm byte bằng `git hash-object --no-filters`** trước khi chạy test. Đây là L-E03 ở dạng
khác: gate đỏ giả vì encoding, và nếu không kiểm byte thì bằng chứng fail-before là rác.

**d) Style và gate có lúc xung đột; ghi ra thay vì tự quyết im lặng.** "Không thêm type hint"
và "không tạo strict error mới" không cùng đúng ở đây. Tôi giữ gate, ghi rõ 3 chú kiểu đã
thêm, và nói thẳng ở §6 để coordinator có thể đảo quyết định — thay vì im lặng phá style **hoặc**
im lặng ship gate đỏ.