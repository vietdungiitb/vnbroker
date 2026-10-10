# SUMMARY — Lát T (TokenManager + 2 endpoint `gaia`)

**Branch:** `feat/t-token` · **Base:** `dev @ 3e252ac`
**Commit code:** `d7d75caf6396459d9007d5c9dba991996a20cf38` (`d7d75ca`)
**Ngày:** 2026-10-10 · **Phạm vi:** GĐ4 của `docs/PLAN_TCBS_ROUND2.md` §2 (T1..T10)

---

## 1. File đã đổi — đúng 3, không đụng file ngoài claim

| File | Hành động | Dòng |
|---|---|---|
| `vnbroker/broker/tcbs/token_manager.py` | **TẠO MỚI** | 303L (ngân sách 400L) |
| `vnbroker/broker/tcbs/auth.py` | sửa | 178L → 306L |
| `tests/unit/broker/tcbs/test_tcbs_token_manager.py` | **TẠO MỚI** | 603L · 50 test |

Lệnh kiểm không có file nào khác bị đụng:

```powershell
git status --short
# M  vnbroker/broker/tcbs/auth.py
# ?? tests/unit/broker/tcbs/test_tcbs_token_manager.py
# ?? vnbroker/broker/tcbs/token_manager.py
git diff --stat HEAD~1
```

`session.py`, `__init__.py`, `client.py`, `test_session_auth.py` — **không đụng**
(đúng `docs/PLAN_TCBS_ROUND2.md` §5).

---

## 2. Gate — đã chạy thật, dán output

Tất cả chạy trong worktree `C:\Mujoco Projects\tcbs-t-token`, `.venv\Scripts\python.exe`.

| # | Lệnh | Baseline `dev@3e252ac` | Kết quả lát T | Exit |
|---|---|---|---|---|
| 1 | `… -m pytest tests/unit/broker/tcbs/ -q -p no:cacheprovider` | `312 passed` | **`362 passed in 6.96s`** | 0 |
| 2 | `… -m pytest tests/contract -q -p no:cacheprovider` | `72 passed` | **`72 passed in 65.07s`** | 0 |
| 3 | `… -m ruff check vnbroker` | `All checks passed!` | **`All checks passed!`** | 0 |
| 4 | `… scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1161, fixed 105).` | **`OK: no new strict errors (baseline 1266, now 1161, fixed 105).`** | 0 |
| 5 | `… scripts/verify_tcbs_coverage.py` | `da noi 39 / chua noi 9` | **`da noi 41 / chua noi 7`** | 0 |
| 6 | `… -m ruff check tests` | `Found 13 errors.` (KNOWN-RED) | **`Found 13 errors.`** — không tăng | 1 (đã biết) |

**Gate 5 đạt đúng mục tiêu bắt buộc**: `39 → 41` đã nối, `9 → 7` chưa nối.
Hai path mới rời khỏi danh sách chưa nối:

```
Path trong spec chua noi vao code:
  - /ananke/v1/securities
  - /api/v1/derivatives/contracts
  - /hydros/v1/account/{accountNo}/pricing-policy
  - /khronos/v1/cash/deposit/update
  - /khronos/v1/cash/withdraw/update
  - /khronos/v1/order/condition/cancel
  - /physis/v1/stock/transfer
```

**Gate phụ (không bắt buộc nhưng đã chạy)** — hồi quy rộng hơn:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --no-header -k "tcbs"
# 541 passed, 7 skipped, 1224 deselected in 14.06s     (baseline 491 passed → +50 test mới)
```

### 2b. Gate **CHƯA CHẠY** — và vì sao đó là kết luận hợp lệ

| Gate | Lý do |
|---|---|
| Probe server TCBS thật (TTL thật của JWT, hành vi thật của `expiredTime`, format `expireDate`) | **Chưa có Smart OTP (iOTP)** — lấy được từ app TCInvest. Mọi endpoint `gaia` đều bắt buộc `otp` (`required: ['apiKey','otp']`). |
| Xác nhận nhánh T7(a) `expiredTime` trên production | **Nhánh chết.** Spec 1.0.0 không có field này. Xem §4. |
| Đo `countBack` / resolution phút (N5) | Cần JWT — ngoài phạm vi lát T. |

⚠ **Không suy ra "chắc là được"** từ test xanh cho phần này. Test chỉ chứng minh
code xử lý đúng input mà test dựng; **hành vi runtime của TCBS chưa quan sát trực tiếp
lần nào**. Đặc biệt: TTL thật của JWT do TCBS phát là **CHƯA BIẾT**.

Lệnh đếm lại P2 (đã dùng để lập luận, tái lập được):

```powershell
.venv\Scripts\python.exe -c "import json;d=json.load(open('docs/references/openapi-v1.0.0.json',encoding='utf-8'));s=json.dumps(d,ensure_ascii=False);print('expiredTime =',s.count('expiredTime'));print('expireDate  =',s.count('expireDate'))"
# expiredTime = 0
# expireDate  = 2
```

---

## 3. Bằng chứng fail-trước / pass-sau (hazard 10)

### Lần FAIL #1 — chỉ có test, chưa có `token_manager.py`

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_token_manager.py -q -p no:cacheprovider --no-header
```

```
tests\unit\broker\tcbs\test_tcbs_token_manager.py:33: in <module>
    from vnbroker.broker.tcbs import token_manager as token_manager_mod
E   ImportError: cannot import name 'token_manager' from 'vnbroker.broker.tcbs'
EXIT=2
```

### Lần FAIL #2 — đã có `token_manager.py`, **`auth.py` CÒN NGUYÊN**

Đây là lần chứng minh **bug F-2** bằng số đo, không bằng mắt:

```
FAILED ...::TestT7AuthenticateExpiryBranches::test_branch_c_no_expired_time_and_no_jwt_does_not_fabricate_8h
AssertionError: session tự chế 8 giờ — bug F-2 chưa chặn.
  token_expires_at=datetime.datetime(2026, 10, 10, 14, 38, 32, 534042)
  sau khi gọi lúc datetime.datetime(2026, 10, 9, 23, 38, 32, 533136, tzinfo=utc)

FAILED ...::TestT7AuthenticateExpiryBranches::test_branch_b_exp_claim_used_when_no_expired_time
  - TypeError: can't subtract offset-naive and offset-aware datetimes
  # token_expires_at là datetime NAIVE ⇒ chính là dấu vết của `datetime.now() + 28800s`
  # thay vì datetime có tz lấy từ claim `exp`.

FAILED ...::TestT8ApiKeyEndpoints::test_get_api_key_expiration_posts_correct_path_and_body
  - AttributeError: 'TCBSAuthService' object has no attribute 'get_api_key_expiration'
  (8 test T8/T9 cùng lý do)

======================== 12 failed, 38 passed in 6.10s ========================
EXIT=1
```

**Đối chiếu con số 8 giờ**: gọi lúc `2026-10-09 23:38:32 UTC`, kết quả
`2026-10-10 14:38:32` (naive, local UTC+7 ⇒ `07:38:32 UTC`). `23:38:32 + 28800s =
07:38:32 UTC`. Khớp tuyệt đối với `expires_in_seconds=28800` ở `session.py:90`.

### Lần PASS — sau khi sửa `auth.py`

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/ -q -p no:cacheprovider --no-header
# ============================= 362 passed in 6.96s =============================
# EXIT=0
```

Kiểm lại hành vi nhánh (c) sau khi sửa, không qua pytest:

```powershell
.venv\Scripts\python.exe -X utf8 -c "… TokenManager(token='opaque-token').is_expired() …"
```
```
token_expires_at sau nhanh (c) = None
token van dung duoc            = 'opaque-token'
TokenManager.is_expired()      = None
```

---

## 4. Trạng thái từng AC

| AC | Đạt? | Bằng chứng |
|---|---|---|
| **T1** decode JWT `exp`/`iat` cục bộ, base64url thiếu padding | ✅ | `TestT1LocalJwtDecode` 5 test. `test_decode_does_not_call_network` monkeypatch `requests.post/get/request` thành `raise AssertionError` ⇒ chứng minh không gọi mạng, không chỉ suy luận. |
| **T2** token không phải JWT ⇒ không crash, `expires_at=None`, vẫn dùng được | ✅ | `TestT2NonJwtToken` — 5 biến thể (1 phần · base64 hỏng · thiếu `exp` · rỗng · `"...."`). |
| **T3** buffer lấy từ `BrokerSession`, không tự đặt hằng | ✅ | `test_buffer_read_from_broker_session` + `test_module_has_no_hardcoded_expiry_constants` (parse AST module, assert **không có** hằng số `300`/`28800`). Đây là assert chống tái phạm, không phải grep. |
| **T4** hết hạn + không provider ⇒ raise kèm hướng dẫn | ✅ | `TestT4ExpiredWithoutProvider` — assert `http_status == 401`, message chứa `"OTP"` và `"TCInvest"`, và message **không chứa token**. |
| **T5** provider gọi đúng 1 lần, cache token mới | ✅ | `test_provider_called_exactly_once_then_cached` — đếm lời gọi qua 3 lần `get_token()`. |
| **T6** `on_expiring` bắn đúng 1 lần | ✅ | `test_callback_fires_once_when_crossing_buffer` — 3 lần `get_token()` ⇒ `len(fired) == 1`. Thêm test callback **reset** khi `set_token()` token mới. |
| **T7** chặn bug 8 giờ, 3 nhánh | ✅ | `TestT7AuthenticateExpiryBranches` 5 test. Xem cảnh báo bên dưới về nhánh (a). |
| **T8** `apikey/info` + `apikey/extend` đúng path + body | ✅ | `TestT8ApiKeyEndpoints` 8 test — assert URL và **payload body** khớp từng field trong spec. |
| **T9** không log token/otp/api_key ở **mọi** level | ✅ | `test_no_secret_in_any_log_level` — `caplog.at_level(DEBUG)`, quét **mọi** record ở mọi level, kiểm cả `repr(record.args)`. **Có assert chống tautology**: `assert len(caplog.records) > 0` và `assert logging.DEBUG <= min(levels)`. |
| **T10** chữ ký `authenticate`/`is_token_valid`/`revoke` không đổi | ✅ | `TestT10PublicSignatureUnchanged` 5 test dùng `inspect.signature`. Chữ ký chụp **trước** khi sửa được ghi trong comment ở `test_tcbs_token_manager.py:541-545`. |

### ⚠ Cảnh báo về nhánh T7(a) — đọc trước khi tin test này

`test_branch_a_expired_time_field_is_used` xanh **không** đồng nghĩa hành vi
production đã kiểm chứng. Spec TCBS 1.0.0 **không có** field `expiredTime`
(đếm `0` lần toàn spec, lệnh ở §2b) ⇒ nhánh này **không reachable từ server thật**.
Giữ lại chỉ để không vỡ tương thích ngược. Docstring của test và của
`_resolve_expires_at` đều ghi rõ điều này.

### Trạng thái nhánh (c) — cách làm không cần sửa `session.py`

`session.py` **không bị sửa** (đúng yêu cầu). Vấn đề: `set_token()` có
`expires_in_seconds: int = 28800` (`session.py:76`), nên truyền
`expires_in_seconds=None` như AC T7 ghi sẽ ném `TypeError` ngay trong
`timedelta(seconds=None)` (`session.py:90`) — chữ ký **bắt buộc phải đổi** để làm
đúng theo nghĩa đen của plan.

Cách đã chọn thay thế, không cần đụng `session.py` — `auth.py:_store_token()`:

```python
self._session.set_token(token, expires_at=expires_at)
if expires_at is None:
    self._session.token_expires_at = None
```

Lý do chấp nhận được: `token_expires_at` là **field công khai** của dataclass
(`session.py:45`, không có tiền tố `_`), và **chính repo này đã làm y vậy** —
`tests/integration/tcbs/test_tcbs_full_acb.py:497`:
`c.session.token_expires_at = None  # No expiration for tests`.

**Hệ quả phải nói thẳng (xem §5, rủi ro R2).**

---

## 5. Rủi ro còn lại

| # | Rủi ro | Mức | Đo được / đánh giá |
|---|---|---|---|
| **R1** | **TTL thật của JWT TCBS chưa biết.** Toàn bộ T1-T7 dựa trên giả định token là JWT 3 phần có claim `exp` kiểu số. Nếu TCBS phát token kiểu khác, `decode_expiry` trả `None` ⇒ rơi vào **nhánh (c)**: session không tự hết hạn ⇒ token chết vẫn dùng tới khi server trả 401. | Cao | **Chưa đo được** — cần Smart OTP. Đây là điểm yếu còn lại của việc "chặn 8 giờ bịa": ta bỏ con số bịa, nhưng chưa thay bằng con số thật. |
| **R2** | Sau nhánh (c), `session.token_expires_at is None` ⇒ `BrokerSession.is_token_expired()` trả **`True`** (`session.py:150-151`), và `check_and_update_state()` (`session.py:172`) sẽ lật session sang `EXPIRED`. | Trung bình | **Đo được, hiện chưa kích hoạt**: `grep -rn "check_and_update_state" vnbroker/` → chỉ khớp **duy nhất** định nghĩa `session.py:161`, **không nơi nào gọi**. Nhưng đây là cái bẫy cho người sau: ai wire `check_and_update_state()` vào request path là nhánh (c) tự giết session. Cần xem lại khi wire. |
| **R3** | `TokenManager` **chưa được nối** vào `auth.py`/`client.py`. `authenticate()` vẫn tự gọi `TokenManager.decode_expiry()` (hàm tĩnh), không dùng instance `TokenManager`. T5/T6 (provider, callback) hiện **chưa có đường vào từ `TCBSAuthService`**. | Thấp (thiết kế) | Có chủ đích: `client.py` là file của coordinator (`PLAN_TCBS_ROUND2.md` §5), và chưa có nơi nào cấp Smart OTP để nối `token_provider`. Để coordinator quyết. |
| **R4** | `from vnbroker.broker.tcbs import TokenManager` **fail** — `__init__.py` chưa export. | Thấp | Đo: `ImportError: cannot import name 'TokenManager' from 'vnbroker.broker.tcbs'`. `__init__.py` là file coordinator giữ (F-5). Import trực tiếp module thì OK. |
| **R5** | 2 endpoint mới **chưa từng chạy** với server thật. Body lấy từ spec nhưng response thật có thể khác. | Trung bình | Cần Smart OTP. Mọi trường response đọc bằng `.get()` ⇒ thiếu field không crash. |
| **R6** | Test T1 dựng JWT bằng `base64.urlsafe_b64encode` của chính stdlib — trùng công cụ với code production, nên **không chứng minh** tương thích với bộ sinh JWT khác. | Thấp | Đã bù: `test_decode_handles_missing_base64url_padding` assert payload **thật sự** không có `=` trước khi decode, để nhánh padding được thực thi chứ không phải no-op. |

---

## 6. Việc thấy ngoài phạm vi — ghi ra, KHÔNG sửa

1. **`session.set_token()` nên đổi chữ ký** `expires_in_seconds: int = 28800` →
   `Optional[int] = None`, và `session.py:87-90` nên để `token_expires_at = None`
   khi `None`. Đó mới là cách sạch chặn F-2; lát T đã chặn bằng workaround.
   **Nằm ngoài claim** (`session.py` bị cấm chạm).
2. **`session.is_token_expired()` trả `True` khi `token_expires_at is None`**
   (`session.py:150-151`) — ngược với ngữ nghĩa "không biết" của
   `TokenManager.is_expired()`. Hai nguồn sự thật cho cùng một câu hỏi
   ("token này còn hạn không?"). Xem R2.
3. **`SESSION_TIMEOUT_SECONDS = 28800` (`session.py:52`) trùng số** với
   `expires_in_seconds=28800` (`session.py:76`) nhưng **khác nghĩa** (timeout
   không hoạt động vs TTL token). Ai đọc lướt rất dễ nhầm.
4. **`TokenManager` chưa export** trong `__init__.py` — coordinator giữ (F-5).
5. **N8 (nợ có sẵn)**: `_post_gaia()` trong `auth.py` là bản `_post` thứ N trong
   `broker/tcbs/`. Lát T **không** gộp — đúng thứ plan §5b(c) chốt.
6. **N7**: `equity.py:523-525` + `derivatives.py:702-705` vẫn gửi `requestId`
   không tồn tại trong spec. Không đụng (ngoài claim).

---

## 7. Bài học cho Stage 8

1. **AC có thể viết sai ở mức chữ ký mà vẫn đúng ở mức ý nghĩa.** T7 bắt truyền
   `expires_in_seconds=None`, nhưng chữ ký hiện tại là `int` ⇒ `TypeError`. Phải
   tách *"ý nghĩa AC"* khỏi *"văn bản AC"*, rồi **ghi rõ mình chọn cách nào và tại
   sao** — im lặng sửa bằng workaround sẽ khiến người đọc tin là plan đã chạy
   đúng. Đây là dạng lỗi audit tệ nhất: code xanh, AC "không đạt", không ai biết.
2. **Bug "số bịa đặt" nguy hiểm hơn bug crash.** F-2 không làm hỏng gì: test cũ
   vẫn xanh, session vẫn `AUTHENTICATED_READ`. Nó chỉ khiến token chết được dùng
   tiếp 8 giờ rồi chết bằng 401 mơ hồ. Vì vậy grep/scan phải tìm **hành vi suy diễn**
   (`else:` ⇒ `now + 28800`), không chỉ tìm chỗ sai.
3. **Test "xanh" không đồng nghĩa "đúng" nếu AC mô tả nhánh chết.** Nhánh (a) xanh
   và **không bao giờ chạm production**. Khi viết test phải **ghi ngay trong
   docstring** nhánh nào không reachable — nếu không, người đọc sẽ tưởng production
   đã được kiểm chứng. Đây là điểm audit F-7/T7 nêu và lát này thực thi.
4. **Đo bug bằng số trước khi sửa.** Lần FAIL #2 in ra `23:38:32 UTC → 14:38:32`
   ⇒ tự chứng minh `+28800s`. Nếu chỉ ghi "test đỏ", không ai biết test đỏ vì lý do
   **đúng** hay vì lý do ngẫu nhiên.
5. **Assert chống tautology.** T9 test log phải có `assert len(caplog.records) > 0`
   — không có nó thì "không lộ secret" đúng luôn kể cả khi logger chết. Tương tự
   `test_decode_does_not_call_network` monkeypatch network thành `raise` thay vì
   chỉ đếm call.
6. **Kiểm encoding ngay sau khi sửa file có dấu.** Một ký tự `U+FFFD` lọt vào
   docstring `auth.py:109` khi ghi bằng tool; lệnh quét 1 dòng bắt được ngay:
   ```powershell
   .venv\Scripts\python.exe -X utf8 -c "import pathlib;print([i+1 for i,l in enumerate(pathlib.Path(p).read_text(encoding='utf-8').splitlines()) if chr(0xFFFD) in l])"
   ```
   Cần chạy **mỗi lần** sửa file tiếng Việt, không phải lúc review.
7. **Đừng tin `repr` của module để suy ra hằng.** T3 test dùng `ast` quét
   `ast.Constant` — grep chuỗi `"300"` sẽ khớp nhầm số hiệu dòng hay timestamp.
8. **Worktree + junction `.venv` hoạt động tốt**, gate chạy đúng như máy chính.
   Nhưng phải nhớ `git config core.hooksPath` trong repo này **rỗng** ⇒ không có
   hook chặn gì; `--no-verify` vẫy bị cấm vì lý do quy trình, không phải vì hook.

---

## 8. Việc còn lại cho coordinator

- [ ] Thêm `TokenManager` vào `vnbroker/broker/tcbs/__init__.py` (`__all__`) — file này cố ý không có chủ riêng (F-5), cả 3 lát đều tạo symbol mới.
- [ ] Quyết định có wire `TokenManager` (instance, có `token_provider`) vào `TCBSAuthService`/`TCBSBrokerClient` không, và `token_provider` lấy OTP từ đâu. Hiện chỉ phần **tĩnh** (`decode_expiry`) được dùng.
- [ ] Mở ticket riêng cho `session.set_token(expires_in_seconds)` + `is_token_expired()` (mục 6.1, 6.2).