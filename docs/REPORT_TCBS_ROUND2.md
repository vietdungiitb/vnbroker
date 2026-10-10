# BÁO CÁO CUỐI — TCBS Round 2: TokenManager (GĐ4) + 9 endpoint (GĐ5)

**Ngày:** 2026-10-10 · **Trạng thái:** **đã merge `dev` và push `origin/dev`** · base đợt này `b18e47b`
**Phạm vi:** `b18e47b..68ab1ce` — 14 commit, 23 file, +8512/−51

> **Câu đầu tiên phải đọc:** mục tiêu *"phủ hết API TCBS"* **gần đạt**:
> spec 48 path, **47 đã nối**, còn **1** (`/api/v1/derivatives/contracts`, cố ý hoãn vì spec
> tự mâu thuẫn). Nhưng **chưa có gì được probe server thật** — xem §5.

---

## 1. Kết quả chính

| Mục tiêu | Kết quả |
|---|---|
| GĐ4 TokenManager | `token_manager.py` 303L — decode JWT `exp`/`iat` cục bộ, cache bộ nhớ, seam `token_provider`, callback `on_expiring`. **Không** tự refresh (spec không có endpoint — §2 P1) |
| GĐ5 9 endpoint | **47/48** path spec đã nối. 9 path của đợt này: 2 `gaia` · 4 tiền/vay · 1 condition/cancel · 1 `ananke/securities` · (+`bars`/`bars-long-term` đã xong ở GĐ1) |
| Bug sống bị chặn | `session.py:87-90` **bịa 8 giờ** hạn token. Nay lấy từ claim `exp`; không decode được thì **không bịa nữa** |
| Bug sống bị chặn | Write 4xx của money **bị trả về y như thành công**. Nay map đủ 400/404/422/429 |

## 2. Phản bác tiền đề — đo bằng spec, không đoán

Kế hoạch cũ (`PROPOSAL_TCBS_REBUILD_20261009.md`) nêu 5 điều sai sự thực:

| # | Tiền đề cũ | Đo được | Hệ quả |
|---|---|---|---|
| P1 | "TokenManager tự refresh trước 5 phút" | Chuỗi `refresh` trong **toàn spec** = **0 lần**. Token chỉ lấy được qua `apiKey + otp` | **AC không thi hành được.** Thay bằng seam `token_provider` |
| P2 | Token response có `expiredTime` | `expiredTime` trong toàn spec = **0 lần** | `auth.py` phải tự decode JWT |
| P2b | *(bản đầu của plan này cũng sai, đã sửa)* | `session.py:87-90` **bịa 8 giờ**, không phải "không hết hạn" | Bug sống, đã chặn |
| P3 | "13 endpoint chưa dùng" | Đếm AST: 48 spec · 39 nối · **9** thật (2 `bars` đã xong, 1 `token` đã dùng, 1 `campaign-management` đã dùng) | Kế hoạch cũ **thừa 4** |
| P5 | *(phát hiện khi audit)* `requestId` là chuẩn | `requestId` trong toàn spec = **0 lần**, nhưng `equity.py:523-525` + `derivatives.py:702-705` **vẫn gửi** | Field hư cấu; lát mới không copy |

**Lệnh tái lập:** `.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py`

## 3. Gate — đo thật, dán output

Baseline đợt 1 (`b18e47b`): 1696 passed / 26 skipped · contract 72 · ruff src 0 · mypy 1266→1161 · ruff tests 13 KNOWN-RED

| Gate | Lệnh | Baseline | Sau round 2 | Exit |
|---|---|---|---|---|
| pytest toàn bộ | `pytest tests/ -q --timeout=300 -p no:cacheprovider` | 1696 passed, 26 skipped | **1881 passed, 26 skipped** (**+185**) | 0 |
| contract | `pytest tests/contract -q` | 72 passed | **72 passed** | 0 |
| ruff src | `ruff check vnbroker` | `All checks passed!` | `All checks passed!` | 0 |
| mypy strict | `scripts/check_mypy_baseline.py` | baseline 1266 → 1161 | baseline 1266 → **1161** | 0 |
| ruff tests | `ruff check tests` | **13 KNOWN-RED** | **13 KNOWN-RED, không tăng** | 1 *(có sẵn)* |
| phủ API | `scripts/verify_tcbs_coverage.py` | 48 / 39 nối / 9 chưa | **48 / 47 nối / 1 chưa** | 0 |

> ⚠ **Flake mạng (không phải lỗi code).** Lần chạy baseline **thứ nhất** ra
> `1 failed, 1695 passed`; chạy lại ra `1696 passed`. Test đỏ là
> `tests/integration/test_news_integration.py` gọi mạng thật `kbbuddywts.kbsec.com.vn`.
> Đây là lần **thứ ba** trong hai đợt liên tiếp mà một lần chạy đơn lẻ dẫn tới kết luận
> sai. **Một lần đỏ không phải kết luận.**

> ⚠ **Tổng số test biến động theo mạng.** `--collect-only` ra `1719 collected`, còn
> `1696 + 26 = 1722`. Module bị `pytest.skip(allow_module_level=True)` khi kiểm tra
> môi trường ⇒ số item thu thập phụ thuộc trạng thái mạng. **Đối chiếu chéo chỉ dùng
> trong cùng một lần chạy.**

## 4. Audit độc lập

`docs/PLAN_AUDIT_TCBS_ROUND2.md` — verdict `AGREE` (sau `NEED_REVISION`).
Audit code độc lập: **0 blocker · 2 major · 13 minor · confidence high**.

| Finding | Mức | Xử lý |
|---|---|---|
| F-1 `money.py` chỉ map 401/403/5xx ⇒ **400/404/422/429 rơi qua, thân lỗi trả về như thành công** | major | ✅ Đã sửa — `bc9d786`. Bằng chứng đo: trên `money.py` bản cũ `90ead64`, 4/4 test **DID NOT RAISE**; bản mới **32 passed** |
| F-2 không chỗ nào kiểm `rc` (TCBS trả HTTP 200 kèm mã nghiệp vụ) | major | ✅ một phần — thêm `describe_business_code()` + ghi rõ vào docstring 3 write method. **Raise tự động hoãn** (xem §6 R2) |
| F-8/F-10 `verify_tcbs_coverage.py` phá được bằng docstring 1 dòng; exit 0 dù path hở | minor | Đã ghi: đây là **inventory script, không phải gate**. Không dùng nó làm cổng ra |
| F-4 `auth.py:271-273` ghi `token_expires_at` **ngoài lock** (race) | minor | Ghi backlog — `session.py` ngoài phạm vi round này |
| F-5 `token_expires_at=None` ⇒ `check_and_update_state()` lập tức `EXPIRED` | minor | Hiện **0 caller** — bẫy đang ngủ |
| F-12 `CLAIMS.md` còn `in-progress` sau merge | minor | ✅ Đã sửa (`68ab1ce`) |

## 5. ⚠ CHƯA CHẠY — không được ghi là PASS

| Việc | Vì sao chưa chạy |
|---|---|
| **Probe server TCBS thật** | **Chưa có JWT** — cần Smart OTP từ app TCInvest. `TCBS_AUTH_TOKEN` trong `.env` là **API key** (48 ký tự `10000928…`), không phải JWT. Lệnh đã lưu: `pwsh -File "$env:TEMP\getjwt.ps1"` |
| **Đo TTL thật của JWT TCBS** | Cần token thật. Đợt này chỉ đọc claim `exp` — **chưa biết** TCBS có phát `exp` không |
| **Xác nhận `subAccountId` rỗng thì bỏ hay gửi `""`** | Lát E chọn **bỏ** (không nằm trong `required`). Chưa có server để xác nhận |
| **Đo lại `countBack` / resolution phút** | Cần JWT. `_TRADING_DAY_RATIO = 0.70` vẫn là **hệ số ước lượng** |
| **Xác nhận 18 path đợt 1 gỡ còn sống trên server không** | 401 chạy trước routing. Gỡ theo quyết định Owner dựa trên tài liệu |
| **CI GitHub Actions** | Job bị từ chối do billing |
| Full pytest của auditor | 3 phút — yêu cầu bỏ qua |

## 6. Rủi ro còn lại (residual risk)

| # | Rủi ro | Mức | Xử lý đã làm |
|---|---|---|---|
| **R1** | **HTTP 200 ≠ thành công.** TCBS trả `rc` nghiệp vụ. Write động tiền có thể "thành công" về HTTP nhưng bị TCBS từ chối | **cao** | Docstring cảnh báo + `describe_business_code()`. **Không** raise tự động: spec không liệt kê đủ tập mã và chưa có JWT để probe — raise theo tập đoán có thể chặn nhầm lệnh hợp lệ |
| **R2** | TTL thật của JWT chưa biết; nếu TCBS **không** phát `exp` thì session không tự hết hạn | trung bình | `is_expired()` trả `None` (không biết) thay vì đoán. Cần JWT để chốt |
| **R3** | `derivatives.py` 852L — **đã vượt** ngân sách; `equity.py` 798L chỉ còn 2L | trung bình | Không thêm dòng nào. Đã ghi N4 |
| **R4** | `requestId` hư cấu vẫn còn trong `equity.py:523-525` + `derivatives.py:702-705` | trung bình | Gỡ ở N7 — **chưa làm** vì `derivatives.py` bị cấm chạm |
| **R5** | Nợ N8: **5 bản `_post`** trùng nhau trong `broker/tcbs/` | thấp | Bắt đầu trả bằng `_write_http.py` (155L). `condition_orders.py` chưa chuyển |

## 7. Ngân sách dòng (`CLAUDE.md:15` — 800L max)

| File | L | Ghi chú |
|---|---|---|
| `derivatives.py` | **852** | ⚠ **đã vượt, có sẵn, ngoài phạm vi** |
| `equity.py` | **798** | chỉ còn 2L — thêm 1 method là vượt |
| `quote.py` | 793 | |
| `websocket.py` | 791 | |
| `money.py` | **773** | 563 → 791 (lát M) → 773 (tách `_write_http`) |
| `client.py` | 772 | 708 → 772 (wire facade) |
| `listing.py` | 421 | 373 → 421 |

## 8. Rollback

```bash
git revert bc9d786          # chỉ fix audit F-1/F-2
git revert f23786f          # chỉ wire facade + export
git revert 8e4f959          # chỉ lát E (condition/cancel + securities)
git revert 90ead64          # chỉ lát M (4 endpoint tiền/vay)
git revert 090034a          # chỉ lát T (TokenManager + 2 endpoint gaia)
```

## 9. Bài học cho Stage 8

1. **Gate tự kiểm sha256 bắt được lỗi ngay khi tạo worktree** — nhưng phải **chạy gate
   trong worktree**, không chỉ ở main tree. `.gitattributes -text` **không** thắng
   `core.autocrlf=true`; phải normalize EOL trong chính gate.
2. **Đọc lại tài liệu cũ là nguồn sai.** "13 endpoint" sai 4; `requestId` là bịa.
   Cả hai đều lộ ra khi **đếm bằng script trên spec**, không phải khi đọc.
3. **Bằng chứng fail-trước trên bản cũ phải chạm đúng tầng lỗi.** Test đầu tiên của tôi
   chỉ assert cấu trúc (`_post` có gọi helper) — xanh ở đúng chỗ sai. Phải viết test
   gọi `deposit_margin(dry_run=False)` với HTTP 400 thì mới ra `DID NOT RAISE`.
4. **Audit đọc code tìm ra lỗi mà AC không nêu.** Cả 4 cảnh báo "ngoài phạm vi" của 3
   agent đều đúng và đều bị đánh giá thấp; 2 lỗi nặng nhất (F-1, F-2) **không ai nêu**
   vì nằm ngoài AC. Lát sau cần AC: *"mọi HTTP 4xx phải map thành `BrokerError`"*.
5. **Test của tôi sai trước khi code của tôi sai.** `test_post_json_chua_authenticate`
   giả định session trống trả `None`; thực tế `session.py:130` **ném** exception.
6. **Sửa của tôi làm hỏng gate của tôi** — wrapper thừa tham số và khai sai kiểu làm
   mypy đỏ; 1 import thừa làm `ruff tests` 13→14. Chạy gate **sau** mỗi lần sửa của
   coordinator, không chỉ sau khi agent xong.