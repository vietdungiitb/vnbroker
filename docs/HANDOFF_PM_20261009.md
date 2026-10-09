# HANDOFF — phiên audit độc lập & sửa P0 (2026-10-09)

**Vai trò phiên này:** PM + System Inspector. Không sửa ý kiến của team, chỉ kiểm chứng
độc lập bằng code và thực thi.

**Trạng thái lúc bàn giao**

| Mục | Giá trị |
|---|---|
| Repo | `C:\Mujoco Projects\vnbroker` |
| Branch | `dev` |
| HEAD | `b28f0df` |
| Working tree | **sạch** (`git status --short` rỗng) |
| Đã push | `51f149b..b28f0df` → `origin/dev` |
| Gate | `pwsh -File scripts/check_all.ps1` → **exit 0** |

Đọc `docs/PM_AUDIT_REPORT_20261009.md` **trước** file này — đây là nhật ký chi tiết,
file này là bản tóm tắt + việc còn dở.

---

## 1. NHẬT KÝ PHIÊN — 4 commit đã merge

| # | Commit | Merge | Nội dung |
|---|---|---|---|
| 1 | `f56751e` | `2c67b3c` | Báo cáo audit độc lập toàn dự án (3 blocker, 12 major, 13 minor, 10 mâu thuẫn doc-vs-code) |
| 2 | `2b76026` | `24e4673` | `scripts/check_all.ps1` — entrypoint gate local + sửa handoff/CLAUDE.md |
| 3 | `12cb29c` | `8cb3e8e` | **PM-01 (blocker)** — write gate chuyển tầng HTTP |
| 4 | `8efc03d` | `b28f0df` | 2 lỗi live probe (`subscribe` im lặng, `msgpack` chưa khai báo) + §11 báo cáo |

Cộng 2 commit nhỏ đóng claim: `0f42a10`, `7d138c5`.

### 1.1 PM-01 — blocker đã đóng

`eeb1965` gate ở `Trade` là đúng 10/10 method, nhưng `Trade.as_openapi_client()` là
method **public** trả `DNSEClient` **không có gate** ⇒ **6 request tiền thật** lọt qua
đường hợp lệ.

Sửa: gate chuyển xuống `DNSEHttpClient.request` — điểm nghẽn duy nhất, quyết định theo
**HTTP verb** nên thêm endpoint mới **không thể quên gate** (gate theo method chính là
cách tái tạo đúng bug vừa vá).

```
fail-before:  6 write request lọt  (test in ra từng URL)
pass-after:   6 → 0               (probe độc lập viết trước khi sửa)
test mới:     11, fail-before 6 failed / 4 passed → 11/11 passed
```

⚠ **Breaking change:** `DNSEClient` giờ cần `enable_write()` cho
`post_order`/`put_order`/`cancel_order`/`replace_order`/`close_position`/`create_trading_token`.
Đọc và `dry_run=True` **không** đổi. Chi tiết `CHANGELOG.md`.

### 1.2 Hai lỗi tìm ra bằng live probe (credential thật)

1. **`subscribe` im lặng với Mapping.** `subscribe({"quote":["ACB"]})` gửi
   `"symbols": []`, server trả `active / symbols: None` ⇒ subscribe thành công với
   **0 symbol**, không cảnh báo. Nay raise `TypeError` kèm lời gọi đúng.
2. **`msgpack` không có trong `pyproject.toml`.** Nay có extra `pip install "vnbroker[msgpack]"`.

Test mới: 9, fail-before 9 failed → 9/9 passed.

---

## 2. NHỮNG THỨ ĐÃ XÁC MINH ĐƯỢC (đừng làm lại)

Owner cấp `DNSE_API_KEY` + `DNSE_API_SECRET` trong `.env` (chưa từng được commit — đã verify
619 commit lịch sử). Probe **chỉ read + WebSocket auth**, không bật write gate.

| Hạng mục | Kết quả |
|---|---|
| HMAC-SHA256 signature | ✅ đúng, không chứa secret |
| WebSocket auth in-band | ✅ `session_id=conn_1791515486322648579` |
| **`rate_limit` shape** | ✅ **đúng như doc**: `{messages_per_second: 100, subscriptions_max: 100}` |
| Subscribe + dữ liệu thật | ✅ **19 frame**/12s — giá ACB 20.3, VNM 57.8, ISIN thật |
| dry_run envelope | ✅ không lọt secret |

⇒ **Bản rewrite WebSocket `95f68e6` chạy thật với server**, không chỉ khớp tài liệu.

**Đã đóng (nghi ngờ của audit, không thành finding):** `subscriptions_max` tính theo **số
kênh**, không phải số cặp. Đo thật: 5 kênh × 100 symbols = **500 pairs** vẫn `active` khi
`cap=100` ⇒ `websocket.py:582` **đúng**. Câu hỏi này đóng, đừng mở lại.

**Đã hạ mức (có bằng chứng):** P0 `async_client.py` TokenBucketRateLimiter trùng lặp
→ **`minor`**. Bản async không bao giờ treo: `capacity=300`, refill 5/s ⇒ có token sau tối
đa 0.2s. `rpm=0` thì `_enabled=False`. Ràng buộc khi sửa: **giữ `__aenter__`/`__aexit__`**,
nếu không `async_client.py:360` sẽ `AttributeError` ngay.

---

## 3. VIỆC CÒN DỞ — theo thứ tự nên làm

### 3.1 CẦN OWNER TRẢ LỜI (chặn mọi thứ khác về DNSE) — `PM-26` major

Host **`openapi.dnse.com.vn` không phản hồi**:

```
openapi.dnse.com.vn/accounts        -> timeout 15.002s   (3/3 lần, curl exit 28)
api.dnse.com.vn/user-service/api/me -> HTTP 401 trong 1.249s   (SỐNG)
ws-openapi.dnse.com.vn/v1/stream    -> HTTP 400 trong 1.220s   (SỐNG)
```

DNS OK (`103.151.242.24`), TCP 443 mở, TLS bị đóng ngay (`unexpected EOF`). Không phải
firewall, không phải DNS.

**Ba khả năng, mỗi khả năng dẫn tới việc khác nhau:**

| Khả năng | Hệ quả |
|---|---|
| DNSE chặn IP/geo từ VN | **Toàn bộ code DNSE OpenAPI hiện tại không dùng được cho người dùng Việt Nam.** Đây là finding lớn hơn 25 method sai path |
| Host đang down | Chờ, không làm gì được |
| Credential thuộc môi trường khác | Cần credential đúng môi trường |

Câu hỏi cụ thể cần Owner trả lời: **credential này thuộc sandbox hay production? IP máy này
có bị DNSE chặn không?** Có cách kiểm tra từ máy Owner (VPN, mạng khác) không?

### 3.2 `PM-02` blocker — secret thật trong docs đang track

Số tài khoản TCBS 11 chữ số + 8 hex ký tự đầu API key trong 3 file **đã track**:

- `docs/TCBS_CONNECTION_TEST_REPORT.md:11,28`
- `docs/CENTRAL_MODIFIED_FILES_AUDIT.md:23`
- `docs/TCBS_INVESTMENT_DATA_DESIGN.md:132,235,249,265`

**Thứ tự bắt buộc: rotate API key TRƯỚC, purge file SAU.** Đảo thứ tự thì 8 hex đã public,
xoá file không còn tác dụng. Repo `PRIVATE`.

### 3.3 `PM-12` blocker — không gate nào chạy

GitHub Actions **không chạy** (job bị từ chối khởi động do billing: *"spending limit needs
to be increased"*). Lần chạy thành công cuối: **2026-10-02**. Từ đó tới nay **74 commit**
merge mà không gate nào chạy. Repo không có required status check nào được enforced.

Đã giảm bớt tác hại bằng `scripts/check_all.ps1` (gate local, 1 lệnh, có exit code thật).
Nhưng **merge vẫn tự do** — cần Owner sửa billing hoặc dùng self-hosted runner.

### 3.4 Còn lại trong backlog (chưa đụng)

| ID | Mức | Việc |
|---|---|---|
| PM-03 | major | `broker/session.py:215` in nguyên văn `api_key` (dòng `:218` thì redact token — mâu thuẫn nội bộ) |
| PM-17 | major | `X-TCBS-APIKEY`, `X-TCBS-SIGNATURE`, `consumer_id` chưa vào `SENSITIVE_KEYS`. HMAC signature TCBS **tái dùng được** để ký |
| PM-04 + PM-05 | major | Hệ thống có **4** chính sách failover chứ không phải 2. Đo được bằng thực thi |
| PM-10 | major | `requires = ["setuptools>=42"]` nhưng dùng PEP 639 — build với `76.0.0` → `ValueError`. Sửa thành `>=77` |
| PM-11 | major | `analytics/indicators.py` import `numpy` nhưng không khai báo |
| PM-16 | minor | `brokerage/guards.py` không phủ `X-TCBS-*`; 2 cơ chế gate (`guards.py` vs `brokerage/guards.py`) hành vi lệch nhau |
| PM-13..PM-15 | major | WebSocket lifecycle: task leak sau reconnect (đo được 8 task thay vì 2), `except Exception` không bắt `CancelledError`, `connection_expired` log "reconnecting" nhưng không reconnect |
| PM-18..PM-25 | minor | Cache `_MAX_DEPTH` collision, `except: pass` không log, registry `clear()` toàn cục, sdist không tất định, encoding `check_dist_contents.py`, `.gitignore` thiếu `.env.local`, 12 file >800 dòng, 38 hàm + 20 class dead |
| P2 | hoãn | 22 endpoint A6 + `match_type` enum. **Điều kiện mở: PM-01 xong** (đã xong) — nhưng nên làm sau khi có tầng 2 credential |
| P3 | minor | Dọn **13** lỗi ruff trong `tests/` (handoff ghi 8 — sai) |
| P1 | blocked | Runtime 8h (`MAX_DURATION_EXCEEDED`), 25 method legacy (cần `DNSE_USERNAME`/`PASSWORD` + OTP), msgpack binary frame (cần `pip install "vnbroker[msgpack]"`) |

---

## 4. HOUSEKEEPING — đã verify, làm được ngay

### 4.1 Dọn 8 worktree cũ

Đã kiểm: **0 file uncommitted, tất cả branch đã merge vào `dev`**. An toàn để xoá.

```powershell
git worktree list
git worktree remove "$env:TEMP\opencode\t1-bulk"
# lap lai cho: t1-failover, t1-fixes-bulk, t1-fixes-cache, t1-netpool,
#             t2-policy, t2-secrecy, t2-trade
git worktree prune
```

⚠ Junction/symlink: dùng `git worktree remove`, **không** `rmdir /s /q`.

### 4.2 `docs/CLAIMS.md` trỏ script không tồn tại

`CLAIMS.md:51-53` trỏ `check-overlap.cjs` ở đường dẫn Hermes cục bộ — **không có trong
repo này** ⇒ kiểm chồng lấn **không chạy được**. Claim registry hiện không có cơ chế thật
sự ngăn chồng file.

### 4.3 Không có protocol file

`docs/AGENT_PROTOCOL.md` không tồn tại. `CLAIMS.md:3-6` tự ghi *"worktree chưa bật (mọi
agent dùng chung working directory)"*, và toàn bộ claim ghi `branch = dev` — tức **commit
thẳng vào nhánh tích hợp**, không có điểm merge, không review được.

Cần tạo `docs/AGENT_PROTOCOL.md` + bật worktree trước đợi agent sau. Phiên này đã dùng
worktree cho chính mình (6 branch riêng, không đụng `dev` trực tiếp).

---

## 5. BÀI HỌC QUY TRÌNH — đừng lặp lại

### 5.1 Ba lỗi của probe, đều tự phát hiện trước khi báo cáo

1. Dùng sai signature `__init__` (nhận `DNSEConfig`, không nhận `api_key=`).
2. **Không `await subscribe()`** ⇒ coroutine không chạy, kết quả `"ACCEPTED"` là **giả** —
   nghĩa là *client không từ chối*, **không phải** *server chấp nhận*. Đã chạy lại.
3. Truyền dict vào `channels` ⇒ `symbols` rỗng, tưởng là bug code; hoá ra lỗi probe.

Hai "phát hiện" về `connect()` trả `False` và `ws.url` không tồn tại **không phải bug**:
`connect()` khai báo `-> None` đúng thiết kế (raise khi thất bại), `ws.url` không phải API
công khai. **Đã bỏ khỏi báo cáo** thay vì để lại.

→ Bài học: một probe cho ra số **phải kiểm chứng số đó có ý nghĩa** trước khi báo. Kiểu dữ
liệu sai vẫn cho ra output trông rất hợp lý.

### 5.2 Negative test của `check_all.ps1` lộ bug trong chính script

Khi inject gate giả exit 1 để chứng minh script FAIL, phát hiện: fallback sang `python`
hệ thống làm **mọi** gate exit 1, và gate đang-đỏ-sẵn bị gán nhầm `KNOWN-RED` vì *"không
có ruff"* ⇒ **hàng rào đỏ vì lý do sai**. Đã thêm preflight interpreter + tool, fail sớm
exit 2, không fallback.

### 5.3 Sửa theo hướng "an toàn hơn" làm hỏng test tốt

Raise `msgpack` ở `__init__` nghe hợp lý nhưng **mâu thuẫn với thiết kế "lazy import"** mà
handoff cố ý chọn, và làm hỏng 2 test có sẵn vốn kiểm protocol đúng. Đã đảo lại, ghi vào
commit message.

→ Trước khi "siết" thêm, hỏi: hành vi cũ có đang bảo vệ thứ gì không?

### 5.4 Số liệu trong handoff của team có 2 chỗ sai, đã sửa

| Handoff ghi | Thực tế |
|---|---|
| "Ruff toàn bộ `tests/` để **8** lỗi" | **13** |
| "**32 method** dùng host `api.dnse.com.vn`" | **25** (AST scan `self._api_base_url`) |

→ Đo lại trước khi tin tài liệu. Sai số này khiến session sau tưởng mình vừa **thêm** lỗi.

### 5.5 `mypy --strict` là no-op — cổng chặn không tồn tại

`mypy vnbroker` và `mypy vnbroker --strict` cho **1207 lỗi y hệt**. `strict = true` trong
`[[tool.mypy.overrides]]` bị mypy nâng thành **global** (`mypy/config_parser.py:582-585`),
trong khi comment `pyproject.toml:146` ghi ngược lại. `CLAUDE.md:7,255` mô tả một cổng chặn
không tồn tại. Gate thật là `scripts/check_mypy_baseline.py`.

---

## 6. LỆNH TÁI LẬP

```powershell
cd "C:\Mujoco Projects\vnbroker"
$py = ".\.venv\Scripts\python.exe"

# 1 lệnh, toàn bộ gate, exit code thật
pwsh -File scripts/check_all.ps1            # ~5 phút
pwsh -File scripts/check_all.ps1 -Quick     # bỏ pytest toàn bộ
pwsh -File scripts/check_all.ps1 -SelfTest  # chứng minh script FAIL khi gate đỏ

# Mốc thực trạng tại b28f0df
& $py -m pytest tests/ -q --timeout=300   # 1434 passed, 30 skipped  -> exit 0
& $py -m ruff check vnbroker tests/unit tests/contract   # All checks passed -> 0
& $py -m ruff check tests                  # 13 errors (KNOWN-RED)  -> 1
& $py -m mypy vnbroker                     # 1207 errors            -> 1
& $py -m mypy vnbroker --strict            # 1207 errors (y hệt)    -> 1

# fat file — dùng splitlines, KHÔNG dùng Measure-Object -Line (sai)
& $py -c "import pathlib;print(sorted(((len(p.read_text(encoding='utf-8').splitlines()),p.as_posix()) for p in pathlib.Path('vnbroker').rglob('*.py') if '__pycache__' not in str(p)),reverse=True)[:12])"

# DNSE: host nao phan hoi
curl.exe -sS -m 15 -o NUL -w "openapi: %{http_code} %{time_total}s`n" https://openapi.dnse.com.vn/accounts
curl.exe -sS -m 15 -o NUL -w "legacy : %{http_code} %{time_total}s`n" https://api.dnse.com.vn/user-service/api/me
curl.exe -sS -m 15 -o NUL -w "ws      : %{http_code} %{time_total}s`n" https://ws-openapi.dnse.com.vn/v1/stream
```

⚠ **CI KHÔNG chạy.** Badge GitHub không phải bằng chứng — job chưa bao giờ chạy. Dùng
`check_all.ps1`. Script in rõ *"CI GITHUB ACTIONS: CHUA CHAY"* ở cuối mỗi lần chạy.

---

## 7. NHỮNG THỨ ĐỪNG TIN

| Nguồn | Vì sao |
|---|---|
| `docs/COMPARE_DNSE_SDK.md` | **Stale 6 commit.** A0/B10 còn đúng; **A5, A7, B-gap đã lỗi thời**. Handoff dặn "đọc file này trước khi sửa endpoint DNSE" ⇒ dẫn vào kết luận cũ |
| `CLAUDE.md:217` | Ghi "`dry_run=True` default cho mọi write" — **sai hướng**. Thực tế 25 method `dry_run=False`; an toàn đến từ `enable_write()` |
| `CLAUDE.md:31-33` | Nói `_normalize_quote_result` là "single enforcement point" — `history` thực tế gọi `normalizer.py:55`, **hai bản sao** |
| `CLAUDE.md:15` | "800 max" — **12 file vượt**, max 1876 |
| `CLAUDE.md:79-80` | "indicators.py currently empty" — thực tế **379 dòng**, 11 hàm, 8 test PASS |
| `CLAUDE.md:118,198` | "1001 tests" — thực tế **1441 collected** |
| `mypy --strict` | No-op, xem §5.5 |
| Mọi badge CI | CI không chạy |

---

## 8. LƯU Ý AN TOÀN

- `.env` có `DNSE_API_KEY` + `DNSE_API_SECRET` thật. **Chưa từng** được commit (đã verify
  619 commit lịch sử), `.gitignore` chặn. **Đừng** in giá trị ra log/báo cáo — dùng
  `Redactor`.
- `.env` chỉ có `DNSE_API_KEY`, `DNSE_API_SECRET`, `DNSE_BASE_URL`, `DNSE_MARKET_TYPE`,
  `TCBS_AUTH_TOKEN`. **Không** có `DNSE_USERNAME`/`DNSE_PASSWORD` ⇒ chưa mở được tầng 2
  (trading token, conditional orders).
- `python-dotenv` **không được cài** và **không khai báo** trong `pyproject.toml`, dù
  `CLAUDE.md:212` nói conftest load `.env`. Đường dẫn bị nuốt trong `except ImportError`.
  ⇒ Đọc `.env` bằng parser thuần, hoặc sửa khai báo.
- Tài liệu hệ thống: `docs/AGENT_PROTOCOL.md` (`vninvest`), `CLAUDE.md` (repo này).

---

## 9. TÓM TẮT MỘT CÂU

Không có blocker ngữ lý chức năng — 1434 test xanh, write gate P0 đã đóng và chứng minh
bằng thực thi (6 → 0), WebSocket đã xác minh chạy thật với server DNSE. Vấn đề còn lại
không nằm ở chất lượng code mà ở ba chỗ: **(1)** `openapi.dnse.com.vn` không phản hồi —
cần Owner trả lời trước khi làm gì thêm về DNSE; **(2)** không có gate nào chạy trong 74
commit qua; **(3)** secret thật trong 3 file docs đang track — rotate trước, purge sau.
