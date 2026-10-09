# PLAN — TCBS Round 2: TokenManager (GĐ4) + 9 endpoint còn thiếu (GĐ5)

**Base:** `dev @ b18e47b` · **Ngày:** 2026-10-10 · **Mode A (delegation), 3 worker**
**Nguồn:** `docs/SUMMARY_TCBS_REBUILD.md` §8 (việc còn nợ) · spec `openapi-v1.0.0.json`
**Spec:** `docs/references/openapi-v1.0.0.json` — sha256 `7f97d27bde1c6f4b…`, OpenAPI 3.0.3,
48 path. **Lần đầu được commit vào repo** — đợt 1 dùng file trong `~/Downloads`, không ai
tái lập lại được nếu không có nó.

---

## 0. Baseline gate — đo tại `b18e47b`, không ước lượng (hazard 6)

| Gate | Lệnh | Exit | Kết quả |
|---|---|---|---|
| pytest toàn bộ | `.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider` | 0 | `1696 passed, 26 skipped` |
| contract | `… -m pytest tests/contract -q` | 0 | `72 passed` |
| ruff src | `… -m ruff check vnbroker` | 0 | `All checks passed!` |
| mypy | `… scripts/check_mypy_baseline.py` | 0 | `no new strict errors (baseline 1266, now 1161)` |
| ruff tests | `… -m ruff check tests` | **1** | ⚠ **13 lỗi KNOWN-RED có sẵn** — không đòi xanh, chỉ đòi không tăng |
| ngân sách 800L | đếm file `>800L` | — | 1 file TCBS vượt: `derivatives.py` 852L (có sẵn) |

**⚠ Bằng chứng flake (không phải lỗi code).** Lần chạy baseline **thứ nhất** ra
`1 failed, 1695 passed`; chạy lại ra `1696 passed, 26 skipped`. Test đỏ là
`tests/integration/test_news_integration.py` gọi mạng thật `kbbuddywts.kbsec.com.vn`.
Đây là lần **thứ ba** trong hai đợt liên tiếp mà một lần chạy đơn lẻ dẫn tới kết luận
sai (xem `SUMMARY_TCBS_REBUILD.md` §4). **Quy tắc cho đợt này: một lần đỏ ≠ kết luận,
phải chạy lại và ghi rõ cả hai lần.**

**⚠ Tổng số test biến động theo mạng — đừng so 2 con số của 2 lần chạy.**
`pytest --collect-only` cho `1719 tests collected`, còn `1696 passed + 26 skipped = 1722`.
Chênh 3 là do module bị **skip ở mức module** (`pytest.skip(allow_module_level=True)`)
khi kiểm tra môi trường/mạng — số item thu thập phụ thuộc trạng thái mạng tại thời điểm
collect. **Đối chiếu chéo chỉ dùng trong cùng một lần chạy.**

### 0b. Ngân sách dòng buộc trực tiếp vào cách lát

Đo bằng `(Get-Content <file> -Encoding utf8).Count`:

| File | L | Hệ quả bắt buộc |
|---|---|---|
| `broker/tcbs/equity.py` | **798** | Thêm 1 method ⇒ **vượt 800L** ⇒ endpoint mới **không** đặt ở đây |
| `broker/tcbs/derivatives.py` | **852** | **Đã vượt** ⇒ tuyệt đối không thêm dòng nào |
| `broker/tcbs/money.py` | 563 | +4 endpoint (~150L) ⇒ ~713L, vẫn dưới ngân sách |
| `broker/tcbs/client.py` | 708 | Chỉ coordinator sửa (facade) |
| `explorer/tcbs/listing.py` | 373 | +1 endpoint, thoải mái |
| `explorer/tcbs/quote.py` | **793** | Chỉ còn 7L — lát sau thêm là vượt im lặng |
| `explorer/tcbs/websocket.py` | **791** | Chỉ còn 9L — như trên |

> Ba file `derivatives.py`/`equity.py`/`quote.py` chỉ còn dưới 1 chút hoặc đã vượt.
> Đây là **nợ kỹ thuật có sẵn**, không phải do đợt này. Xem N4.

---

## 1. ⚠ Phản bác tiền đề của kế hoạch cũ (đo bằng spec, không đoán)

`PROPOSAL_TCBS_REBUILD_20261009.md` §6 (Giai đoạn 4) và §7 (F7) **không còn đúng**:

| # | Tiền đề cũ | Thực tế trong spec | Hệ quả |
|---|---|---|---|
| **P1** | "TokenManager tự refresh trước 5 phút" | **Spec KHÔNG có endpoint refresh token.** Chỉ có `POST /gaia/v1/oauth2/openapi/token` = `apiKey + otp` (Smart OTP từ app TCInvest). Đếm từ khoá `refresh` (không phân biệt hoa thường) trong **toàn bộ** spec = **0 lần** | **AC không thể thi hành** (hazard 6). Phải thay bằng cơ chế *seam* — xem §2 |
| **P2** | Token response có `expiredTime` | Response 200 chỉ có **`token`**. Đếm `expiredTime` trong toàn spec = **0 lần** | `broker/tcbs/auth.py:118` `_parse_expires(data.get("expiredTime"))` **luôn trả `None`** — xem P2b |
| **P2b** | *(bản đầu của plan này sai — đã sửa theo audit)* ~~⇒ session không bao giờ tự hết hạn~~ | **SAI.** `auth.py:128` gọi `session.set_token(token, expires_at=None)`; `session.py:87-90` rơi vào nhánh `else` ⇒ `token_expires_at = now + 28800s` | ⚠ **Bug sống**: session hết hạn sau **8 giờ bịa đặt**, không liên quan gì TTL thật của TCBS. Hậu quả: token chết vẫn được dùng ⇒ mọi request sau đó 401 từ server thay vì `BrokerSessionExpiredError` sạch. **T7 phải chặn cái này** |
| **P3** | "13 endpoint chưa dùng" | Đếm bằng script: spec **48** path, **39 đã nối**, **9 chưa** (trong đó `bars`/`bars-long-term` đã nối ở GĐ1 qua hằng `_BARS_*_PATH`, `gaia/…/token` dùng hằng `_AUTH_PATH`) | Kế hoạch cũ **thừa 4** |
| **P4** | `apikey/extend` là "gia hạn" | Gia hạn **API key**, không phải JWT — **và cũng cần `otp`** (`required: ['apiKey','otp']`) | Không dùng được để refresh token |
| **P5** | *(phát hiện khi audit — không có trong plan cũ)* Mọi write endpoint của TCBS đều cần `requestId` | **Đếm `requestId` trong toàn spec = 0 lần.** `POST /akhlys/v1/accounts/{accountNo}/cancel-orders` chỉ có `{ordersList}`. Nhưng `equity.py:523-525` **vẫn gửi** `requestId`, `derivatives.py:702-705` cũng gửi | ⚠ **Tiền đề sai có sẵn** trong code. Lát M **không được** copy pattern này. Sửa `requestId` ở `equity.py`/`derivatives.py` **ngoài phạm vi đợt này** ⇒ N7 |

**Lệnh tái lập P1..P5** (tự kiểm sha256, lệch là exit 1):
```powershell
.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py
```
Kết quả đo tại `b18e47b`: `spec 48 | da noi 39 | chua noi 9 | _REMOVED_PATHS 18 key,
van con trong spec: 0`. Con số cuối **xác nhận lại lát a3 đợt 1 gỡ đúng 18/18**.

### 1b. Spec phải nằm trong repo — đã sửa

`docs/references/openapi-v1.0.0.json` (sha256 `7f97d27b…42bd4a`, 136.199 B) **đã được
commit** trong đợt này. Trước đó nó chỉ nằm ở `~/Downloads` ⇒ đợt 1 chạy được nhưng
**không ai tái lập lại được**.

Thư mục `docs/references/` bị `.gitignore:213` chặn **cố ý** (chứa credential thật).
Sửa bằng `docs/references/*` + `!docs/references/openapi-v1.0.0.json` ⇒ chỉ mở **đúng
1 file**, các file khác (kể cả `dnse_credentials.txt`, `tcbs_auth_token.txt`) vẫn bị ignore.
Spec đã quét: **0 jwt · 0 bearer · 0 apiKey value · 0 chuỗi hex ≥32**.

⚠ File spec **cũ** `docs/references/tcbs_iflash_openapi.json` (75.678 B, OpenAPI
**3.1.0**, sha `33db1427…`) là bản **trước 1.0.0**, untracked, và nó **có đủ 18 path
`/erebos/*`** mà đợt 1 đã gỡ. Đối chiếu nhầm file này sẽ kết luận ngược "gỡ nhầm 18
endpoint". **Xoá khỏi đĩa** ở commit này.

### 1c. Audit độc lập — `AGREE` sau khi sửa

`docs/PLAN_AUDIT_TCBS_ROUND2.md`, verdict ban đầu **NEED_REVISION**. Đo lại **7/7 gate rẻ
khớp tuyệt đối** và **4/4 tiền đề đúng về dữ kiện**. Đã sửa hết blocker + major:
F-1 (spec vào repo) · F-2 (P2b) · F-3 (chốt cách đặt `condition_orders.py`) ·
F-4 (số test biến động) · F-5 (`__init__.py` có chủ) · F-6/P5 (`requestId` là hư cấu) ·
F-7 (T10 trỏ vào test không tồn tại) · F-8 (thêm 2 file vào bảng ngân sách).

---

## 2. GĐ4 — TokenManager (thiết kế ĐÃ SỬA so với proposal)

**Đổi tên để trung thực:** đây **không phải** "refresh tự động". Đây là
**quản lý vòng đời token không cần mạng** + **seam** cho người gọi cấp token mới.

| # | AC | Kiểm chứng được |
|---|---|---|
| T1 | Decode JWT `exp`/`iat` **cục bộ**, không gọi mạng, base64url + padding lệch | unit test với token dựng trong test |
| T2 | Token không phải JWT (1 phần, base64 hỏng, thiếu `exp`) ⇒ **không crash**, `expires_at=None`, vẫn dùng được | unit test 3 biến thể |
| T3 | **Dùng `BrokerSession.TOKEN_REFRESH_BUFFER_SECONDS` (`session.py:51` = 300) làm nguồn duy nhất.** TokenManager **không** tự đặt hằng 300 — `session.py:120-128` đã áp buffer này rồi; đặt thêm là 2 nguồn sự thật cho một khái niệm | unit test assert đọc đúng hằng từ `BrokerSession`, **không** có hằng trùng lặp trong file mới |
| T4 | Hết hạn **không có provider** ⇒ ném `BrokerSessionExpiredError` **kèm hướng dẫn** ("cần Smart OTP mới"), **không** im lặng trả rỗng | unit test |
| T5 | Có `token_provider` callable ⇒ gọi **đúng 1 lần**, token mới được cache, không gọi lại khi còn hạn | unit test bộ đếm lời gọi |
| T6 | Callback `on_expiring` bắn **đúng 1 lần** khi qua ngưỡng buffer, không bắn lại mỗi lần đọc | unit test |
| T7 | **Chặn bug 8 giờ bịa (P2b).** `authenticate()` truyền `expires_at` **từ JWT `exp`** khi server không gửi `expiredTime`. Khi JWT **không decode được** ⇒ `expires_at` từ `expiredTime` nếu có, nếu không **truyền `expires_in_seconds=None`** để session **không** tự chế 8 giờ; `TokenManager.is_expired()` trả `None` (không biết) ⇒ **để caller quyết**, thay vì im lặng giả định | unit test cả 3 nhánh: (a) có `expiredTime` (b) chỉ có JWT `exp` (c) không có cái nào |
| T8 | **`apikey/info`** + **`apikey/extend`** nối đúng path + body theo spec | unit test mock |
| T9 | **KHÔNG log token/otp/api_key** ở bất kỳ level nào (giữ đúng `SECURITY RULES` đầu `auth.py`) | test `caplog` ở **mọi** level + assert không có giá trị token trong log |
| T10 | **Chữ ký `authenticate` / `is_token_valid` / `revoke` không đổi.** Đo bằng `inspect.signature` **trước và sau**, khẳng định bằng assert chứ không bằng mắt. Test thật của nhóm này là `tests/unit/broker/tcbs/test_session_auth.py` (288L) — **`tests/contract/` không có file TCBS nào** (đã đếm: 6 file, 0 TCBS) | unit test + `inspect.signature` |

> **AC này nói rõ điều KHÔNG làm:** TokenManager **không** tự lấy token mới.
> Không có endpoint để làm việc đó (P1). Seam là `token_provider` do **người gọi** cấu.
>
> **Nhánh `expiredTime` của T7 là nhánh chết với server thật** (spec không có field đó).
> Vẫn giữ nhánh để tương thích ngược, nhưng test phải **ghi rõ** nó không reachable từ
> spec — đừng báo "đã kiểm chứng hành vi production" cho nhánh này.

## 3. GĐ5 — 9 endpoint, chia 2 lát

### S-M — `money.py` (tiền / vay)

| Path | Verb | Ghi? | AC |
|---|---|---|---|
| `/hydros/v1/account/{accountNo}/pricing-policy` | GET | – | M1: `productId` tuỳ chọn **không** gửi khi `None`; validate `account_no` qua `_validate_account_no` |
| `/khronos/v1/cash/deposit/update` | POST | **✓** | M2: `@write_gate`, `dry_run=True` mặc định, validate `amount > 0` **trước** gate |
| `/khronos/v1/cash/withdraw/update` | POST | **✓** | M3: như M2 |
| `/physis/v1/stock/transfer` | POST | **✓** | M4: `description` là **bắt buộc** theo spec ⇒ validate không rỗng |

| # | AC chung lát S-M |
|---|---|
| M5 | **Cả 3 write endpoint đi qua `@write_gate`** — gọi `dry_run=False` khi chưa `enable_write()` ⇒ `BrokerPermissionError`, **không** gửi HTTP. Đã chạy thử bởi auditor ở plan trước ⇒ xác nhận hoạt động |
| M6 | Body đúng **tên field trong spec** (`accountId`/`subAccountId`/`amount`/`paymentContent`; `sourceAccountNumber`/`destinationAccountNumber`/`amount`/`description`). **KHÔNG** thêm `requestId` — **không tồn tại trong spec** (đếm 0 lần, xem P5) |
| M7 | Đọc mọi field response bằng `.get()` (F6: field null **không xuất hiện** trong JSON) |
| M8 | `money.py` sau thay đổi **≤ 800L** |
| M9 | Docstring đầu file nói "RULE: Không có write method" ⇒ **phải sửa** thành đúng |

> **`requestId` là hư cấu — lát M KHÔNG được copy.** `equity.py:523-525` và
> `derivatives.py:702-705` đang gửi field không có trong spec. Sửa chúng **ngoài phạm vi
> đợt này** (N7) vì `derivatives.py` bị cấm chạm và `equity.py` còn 2L dưới ngân sách.
> Nhưng lát M **không được lấy `equity.py` làm mẫu** cho các write method mới.
>
> `@write_gate` đọc `dry_run` từ **`kwargs`** (`guards.py:46`) ⇒ mọi write method mới
> **bắt buộc** khai `dry_run` là **keyword-only** (`*, dry_run: bool = True`), nếu không
> caller truyền vị trí sẽ không bao giờ được gate.

### S-E — condition order + securities

| Path | Verb | Ghi? | AC |
|---|---|---|---|
| `/khronos/v1/order/condition/cancel` | POST | **✓** | E1: body đúng spec `{accountId, subAccountId, orderNo}` — **không** `requestId` (spec không có) |
| `/ananke/v1/securities` | GET | – | E2: `fields`/`filter` là **query param**, `filter` dạng `symbol=TCB`; bỏ trống ⇒ không gửi |

| # | AC chung lát S-E |
|---|---|
| E3 | Module mới `condition_orders.py` — **`equity.py` 798L không được vượt 800** |
| E4 | `@write_gate` cho `cancel_condition_order`, `dry_run=True` mặc định |
| E5 | `/ananke/v1/securities` **trả raw dict**, **không** ép DataFrame — response schema trong spec **rỗng** (`{}`), bịa cột là hư cấu. Docstring phải ghi rõ *"shape chưa được tài liệu hoá"*. |

---

## 4. Cố ý KHÔNG làm (có lý do, ghi để session sau không vấp)

| # | Việc | Lý do |
|---|---|---|
| N1 | `/api/v1/derivatives/contracts` | Spec **tự mâu thuẫn**: path REST `/api/v1/…`, `summary` = *"Price board (WSS, derivative)"*, `description` = *"over WebSocket"*, response **không có `content`**. Không định nghĩa được AC có ý nghĩa (hazard 8). **Cần Owner xác nhận REST hay WS** |
| N2 | Auto-refresh token | Không có endpoint (P1) |
| N3 | Probe server thật | Chưa có JWT — cần Smart OTP từ app TCInvest |
| N4 | Tách `derivatives.py` 852L | Ngoài phạm vi; nhưng **không thêm** dòng nào vào file này |
| N5 | Đo lại `countBack` / resolution phút | Cần JWT |
| N6 | Gỡ `/aion/v1/accounts` | Owner đã chốt **giữ làm ngoại lệ** (`@abstractmethod get_account_list`) |
| N7 | Gỡ `requestId` hư cấu khỏi `equity.py:523-525` + `derivatives.py:702-705` | Phát hiện P5. `derivatives.py` bị cấm chạm; `equity.py` chỉ còn 2L dưới ngân sách. **Mở ticket riêng** |
| N8 | Gộp 4 bản `_post`/`_write_request` trôi dạt trong `broker/tcbs/` thành 1 | Nợ có sẵn: `derivatives.py:711`, `money.py:509`, `equity.py`, và file mới của lát E. Xem quyết định F-3 ở §5 |

---

## 5. Slicing — 3 lát **không chung file** (§0.5)

| Agent | Branch | Phạm vi | File **duy nhất** được sửa |
|---|---|---|---|
| **T** | `feat/t-token` | GĐ4 TokenManager + 2 endpoint `gaia` | `vnbroker/broker/tcbs/token_manager.py` **(mới)**, `vnbroker/broker/tcbs/auth.py`, `tests/unit/broker/tcbs/test_tcbs_token_manager.py` **(mới)** |
| **M** | `feat/m-money` | 4 endpoint tiền/vay | `vnbroker/broker/tcbs/money.py`, `tests/unit/broker/tcbs/test_tcbs_money_endpoints.py` **(mới)** |
| **E** | `feat/e-cond-sec` | condition/cancel + securities | `vnbroker/broker/tcbs/condition_orders.py` **(mới)**, `vnbroker/explorer/tcbs/listing.py`, `tests/unit/broker/tcbs/test_tcbs_condition_order.py` **(mới)**, `tests/unit/explorer/tcbs/test_tcbs_ananke_securities.py` **(mới)** |

**Kiểm tra rời nhau bằng script, không bằng mắt:** `T ∩ M = ∅`, `T ∩ E = ∅`, `M ∩ E = ∅`.

### 5b. Quyết định thiết kế — vì sao `condition_orders.py` mới, không nhét vào `derivatives.py` (F-3)

Audit nêu mâu thuẫn: `derivatives.py` **đang giữ** 3 endpoint cùng họ condition-order
(`condition/place` `:46`, `v2/condition/change` `:48`, `condition/detail` `:44`) và có sẵn
`_write_request` 69L (`:714-782`). Tách riêng 1 thành viên ra khỏi gia đình, chỉ để né
file 852L, là **nhân bản thay vì refactor**.

Ba lựa chọn, coordinator chọn **(c)**:

| | Cách | Đánh giá |
|---|---|---|
| (a) | Thêm vào `derivatives.py` | 852 → ~880L. **Vượt thêm**, vi phạm N4. ❌ |
| (b) | Tách `_http_write.py` dùng chung, sửa `derivatives.py` để dùng | Giảm `derivatives.py` xuống dưới 800L — **có lợi thật** — nhưng là refactor file 852L trong đợt đang làm feature. Rủi ro cao hơn giá trị. ❌ |
| **(c)** | **`condition_orders.py` tự mang `_post` riêng** | Không đụng file nào bị cấm. **Trùng lệnh với `money.py`/`equity.py`/`derivatives.py` vốn đã mỗi file một bản `_get`/`_post`** ⇒ theo đúng house style sẵn có, không tạo nợ mới. Nợ nhân bản ghi ở **N8**. ✅ |

**Nếu lát E copy `_post` từ `derivatives.py` thì phải copy đúng, không cải tiến âm thầm** —
cải tiến là refactor, cấm. Chỉ lấy phần **cần thiết cho 1 method POST**.

**Coordinator giữ (không agent nào sửa):**
`vnbroker/broker/tcbs/client.py` (facade — wire service mới + wrapper),
`vnbroker/broker/tcbs/__init__.py` (export service mới),
`docs/**`, `docs/references/**`, `scripts/**`, `.gitignore`, `CHANGELOG.md`.

> `__init__.py` phải vào danh sách này vì cả 3 lát đều tạo symbol mới cần vào `__all__`;
> để ngỏ thì 3 agent tranh nhau sửa, hoặc service mới không được export ⇒
> `from vnbroker.broker.tcbs import X` fail (F-5).
>
> `client.py` là file 708L: gộp 3 hunk của 3 agent vào 1 commit là weld, mất khả năng
> revert từng lát. Coordinator gộp trong commit hợp nhất sau khi đã merge từng lát riêng.

---

## 6. Nguyên tắc bắt buộc cho cả 3 agent

1. **Không** dùng `git checkout -- <file>` để thử nghiệm (hazard 11).
2. **Không** dùng `--no-verify`.
3. Test mới phải chứng minh **fail trước, pass sau** (hazard 10).
4. Mọi con số trong `docs/SUMMARY_<agent>.md` phải kèm lệnh tái lập được.
5. File có dấu: đọc bằng `Get-Content -Encoding utf8` (hazard 5).
6. Agent viết `docs/SUMMARY_<agent>.md` **trước** khi supervisor hành động.
7. **Không** sửa file ngoài claim. Thấy vấn đề ngoài phạm vi ⇒ **ghi ra, không sửa**.
8. `derivatives.py` **không được chạm**. `equity.py` không được vượt 800L.

## 7. Rollback

```bash
git revert <merge-sha-t>   # chỉ TokenManager
git revert <merge-sha-m>   # chỉ endpoint tiền
git revert <merge-sha-e>   # chỉ condition order + securities
```