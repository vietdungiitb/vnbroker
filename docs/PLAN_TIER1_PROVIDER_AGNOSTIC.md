# KẾ HOẠCH — Tier-1 provider-agnostic: một nguồn sự thật + dữ liệu đúng bất kể provider

**Ngày:** 2026-10-10 · **Base:** `dev @ 914fc02` · **Repo:** `vnbroker`
**Audit đầu vào:** `docs/REPORT_TIER1_EXPLORER_SURVEY.md`
**Lessons áp dụng:** L-E01 (số đo, không đoán) · L-G05 (cổng phải phủ hết dạng code) ·
L-G06 (map toàn cục gây va chạm) · L-G07 (gate báo xanh giả) · L-P03 (import vòng)

---

## 0. Chế độ thực thi — và lý do

**Mode B (self-supervised, tuần tự) cho phần ghi code; multi-agent cho phần audit.**

Lý do, nêu thẳng thay vì chọn mặc định: các lát cắt chạm đúng những file đường
gây tiền (`core/source_router.py`, `common/data.py`, `core/utils/transform.py`).
Hazard 1 của skill — hai agent commit cùng một file — **tái tạo nguyên hiểm** khi đã
chia nhỏ hunk. Với thư viện liên quan tiền, ưu tiên là **một người viết, hai người
kiểm tra độc lập** — đúng lý do skill nêu: *"Treat a second agent as a second opinion |
same file, same tool, same misreading"*.

Agent độc lập được dùng ở 3 điểm, đều **read-only**:
- Stage 2 — audit kế hoạch
- Stage 5 — audit mã sau khi viết
- Stage 6 — kiểm chứng độc lập kết quả gate

---

## 1. MÂU THUẪN CẦN CHỐT TRƯỚC — tài liệu kiến trúc vs yêu cầu Owner

`CLAUDE.md` đã tuyên bố nguyên tắc đúng như Owner mong, **nhưng loại TCBS/DNSE khỏi
Tier-1** và **ghi 2 điều mà code không làm được**:

| # | `CLAUDE.md` ghi | Code thực tế | Xử lý |
|:--|:--|:--|:--|
| 1 | `:35` *"rotates on rate-limit / connection loss"* | `x-ratelimit` đọc **0** lần | Sửa **Wave 3** (chưa gấp, xem §6) |
| 2 | `:38` *"Providers: VCI, KBS (no auth required)"* | Owner muốn **TCBS + DNSE** vào Tier-1 | **Thay đổi thiết kế** — xem dưới |
| 3 | `:44-45` *"`_normalize_quote_result` … single enforcement point"* | Có **2** bản trùng lặp; `api/quote.py` **không** đi qua | Sửa **Wave 1** |

**Mục 2 là thay đổi kiến trúc, không phải sửa lỗi.** Owner đã yêu cầu rõ
("TCBS và DNSE có sẵn api key trong env nên có thể tự động đưa vào provider list")
⇒ kế hoạch này **thực hiện** thay đổi đó và **cập nhật `CLAUDE.md`** cho khớp.

**Rủi ro phải nói trước khi làm:** TCBS/DNSE là **Tier-2 broker** — có key, có
quota, có rủi ro 429 cao hơn VCI/KBS. Đưa chúng vào Tier-1 có nghĩa là
**lưu lượng người dùng ăn vào quota broker của Owner**. Wave 2 bắt buộc phải:
- chỉ dùng chúng **khi có credential trong env** (không đụng tới khi không có);
- có **cooldown riêng** để không kéo rate-limit của broker xuống;
- **không** ghi key ra log.

---

## 2. BASELINE GATE — mã trước khi đòi bất cứ điều gì

Đo tại `914fc02`. Hazard 6: **không được đòi PASS của một gate vốn đang đỏ.**

| Gate | Lệnh thật | Exit @ baseline |
|:--|:--|:--|
| ruff | `.venv\Scripts\python.exe -m ruff check vnbroker scripts tests/unit` | **0** |
| mypy | `python scripts/check_mypy_baseline.py` | **0** (baseline 1266 → now 1138) |
| contract | `pytest tests/contract -q` | **0** (72 passed) |
| pytest toàn bộ | `pytest tests/ -q` | **0** (1923 passed, 26 skipped) |
| lessons | `python scripts/check_lessons.py` | **0** (24/40) |
| tcbs-bodies | `python scripts/check_tcbs_bodies.py` | **0** |
| **Tổng** | `pwsh -File scripts/check_all.ps1` | **0** — 8/8 PASS |

Hai gate **không tồn tại, sẽ phải tạo** (mục tiêu của kế hoạch này):

| Gate mới | Chặn cái gì |
|:--|:--|
| `scripts/check_provider_consistency.py` | 3 danh sách provider mâu thuẫn; provider có credential chưa vào AUTO |
| test contract đa provider | Cột lệch giữa VCI/KBS/TCBS/DNSE |

---

## 3. AC — đo đúng thứ người dùng quan tâm (hazard 8)

> *Nếu AC pass nhưng tính năng vẫn vô dụng, AC có bắt được không?*

| AC | Given/When/Then | Chống proxy |
|:--|:--|:--|
| **AC-1** | Gọi `Vnbroker(source="AUTO").Quote.history("TCB")` **không truyền provider**, có `DNSE_API_KEY`+`SECRET` trong env ⇒ **dữ liệu trả về giống hệt** lúc đặt `source="KBS"` (so sánh tập cột + tz + dtype) | Không chấp nhận "list chứa DNSE" là đủ — phải **so dữ liệu thật** |
| **AC-2** | `intraday()` từ **mọi** provider ⇒ cùng một tập cột, `match_type` có mặt ở DNSE | Không dựng frame giả rồi kiểm hàm (lỗi của `test_match_type_contract.py:34-43`) |
| **AC-3** | `get_auto_candidates(m)` cho mọi module mà registry có provider ⇒ **không rỗng** | Chỉ kiểm `quote` là thiếu — lỗi gốc ở `screener/indices/live` |
| **AC-4** | Không có credential ⇒ provider đó **không** xuất hiện trong `AUTO` | Không chỉ kiểm "đăng ký trong registry" |
| **AC-5** | `BulkRouter.fetch_history` qua **2 provider thật** ⇒ tz đồng nhất, `pd.concat` **không** rơi về `dtype object` | Không gọi thẳng `Normalizer` như `test_failover_integration.py:119` đang làm |
| **AC-6** | `market_cap` với `price_unit=None` ⇒ **không** lệch 1000 lần so với `price_unit="VND"` khi provider trả giá VND | Phải test tới `_compute_market_cap` thật, không patch nó đi |

**Ràng buộc chống tự lừa (hazard 10):** mỗi test mới phải **đỏ trên file trước khi sửa**.
Cách làm: `git show 914fc02:<file> > <file>` → chạy test (kỳ vọng đỏ) → khôi phục.
**Không** dùng `git checkout --` (Hazard 11).

---

## 4. WAVE 1 — Một nguồn sự thật về provider

**File (rời nhau với Wave 2):** `core/provider_pool.py`, `core/registry.py`,
`core/source_router.py`, `vnbroker/__init__.py`, `CLAUDE.md:38`

| Việc | Nguyên nhân |
|:--|:--|
| W1.1 `ProviderPool` đọc **đúng biến `.env` thật** cho TCBS | `TCBS_API_SECRET` không tồn tại; `.env` chỉ có `TCBS_AUTH_TOKEN`/`TCBS_OPENAPI_API_KEY` |
| W1.2 `get_auto_candidates()` **hỏi pool** thay vì list cứng | `source_router.py:28-35` list cứng ⇒ DNSE/TCBS không bao giờ vào AUTO |
| W1.3 Thêm `indices`/`live`/`screener` vào AUTO | hiện trả `[]` dù registry có provider |
| W1.4 Cổng `check_provider_consistency.py` + self-test âm | chặn tái phát 3 danh sách mâu thuẫn |
| W1.5 Sửa `CLAUDE.md:38` | khớp với quyết định Owner |

**Không** thêm giới hạn ưu tiên cho TCBS/DNSE ở Wave 1 — chưa có số đo.

---

## 5. WAVE 2 — Dữ liệu đúng bất kể provider  ⟵ **ĐẢO LÊN SỐ 1**

> **Đảo thứ tự sau khảo sát lần 2** (`docs/AUDIT_TIER1_RECHECK_20261010.md`):
> chạy thật cho thấy **KBS và VCI — hai provider DUY NHẤT đang nằm trong `AUTO` — trả về
> khác nhau**: KBS tz-**naive** + `match_type` **thường**; VCI tz-**aware** + **hoa**.
> Đo được: `pd.concat` → `dtype=object`; `df[df.match_type=="Buy"]` → KBS **0 dòng**,
> VCI **5 dòng**. Lỗi này **đang xảy ra với người dùng hôm nay**, không cần TCBS/DNSE.
> ⇒ Wave 2 lên trước Wave 1.

**File:** `core/utils/transform.py`, `core/utils/normalizer.py`, `api/bulk.py`,
`api/snapshot.py`, `common/data.py`

| Việc | Nguyên nhân |
|:--|:--|
| W2.1 Ép `match_type` về một dạng duy nhất | KBS `buy` vs VCI `Buy` — **đo được** |
| W2.2 Ép `time` về tz-aware `Asia/Ho_Chi_Minh` | KBS naive vs VCI aware — **đo được** |
| W2.3 Chuẩn hoá trong `BulkRouter` | `api/bulk.py:114-115` chỉ `pd.concat` |
| W2.4 Chốt đơn vị giá, sửa `multiplier` | `snapshot.py:358` ×1000 vs cả 3 provider khai VND |
| W2.5 Xoá 1 trong 2 bản chuẩn hoá trùng | `normalizer.py:55-78` == `data.py:838-881` |
| W2.6 `api/quote.py` đi qua cùng tầng chuẩn hoá | không gọi `Normalizer` — **đo bằng script** |

⚠ **W2.4 cần Owner xác nhận đơn vị thật** trước khi sửa (Q2).
**W2.1, W2.2, W2.3, W2.5, W2.6 làm được ngay** — không phụ thuộc câu trả lời đó.

## 1b. Wave 1 (sau Wave 2) — nối TCBS vào Tier-1, nguyên nhân đã rõ

> Khảo sát lần 2 đã **tìm ra nguyên nhân gốc**, không còn là giả định:
> `explorer/tcbs/auth.py` đọc `TCBS_AUTH_TOKEN` (**48 ký tự, KHÔNG phải JWT**) và
> `TCBS_OPENAPI_API_KEY` (**.env không có**). Biến `TCBS_JWT_TOKEN` (**JWT thật, 1290 ký tự**)
> xuất hiện **0 lần** trong `auth.py`. Probe trực tiếp: JWT đó gọi
> `/tartarus/v1/tickerCommons` → **HTTP 200, dữ liệu thật**.
>
> ⇒ Owner đúng: **TCBS ổn định**, thư viện **nối sai biến**. Sửa nhỏ, giá trị lớn.

| Việc | Nguyên nhân |
|:--|:--|
| W1.0 `resolve_auth_token()` ưu tiên `TCBS_JWT_TOKEN` khi có | **đo được** — đây là thứ làm TCBS hỏng |
| W1.1 `ProviderPool` đọc biến `.env` thật cho TCBS | `TCBS_API_SECRET` không tồn tại |
| W1.2 `get_auto_candidates()` **hỏi pool** thay vì list cứng | DNSE có key hợp lệ vẫn không vào AUTO |
| W1.3 Thêm `indices`/`live`/`screener` vào AUTO | hiện trả `[]` dù registry có provider |
| W1.4 Cổng `check_provider_consistency.py` + self-test âm | chặn tái phát 3 danh sách mâu thuẫn |

---

## 6. WAVE 3 — Rate-limit thật (sau Wave 1&2, có lý do)

| Việc |
|:--|
| W3.1 Đọc `X-RateLimit-*` / `Retry-After` → nạp `cooldown_until` |
| W3.2 **Không retry** khi gặp 429 — chuyển provider ngay |
| W3.3 Bật token-bucket **hoặc** xoá 15 test đang bảo vệ code chết |

**Đi sau vì có lý do:** rate-limit chỉ hữu ích khi router đã thấy provider nào còn quota.
Sửa Wave 1 trước, nếu không thì vẫn chỉ có 2 provider trong `AUTO`.

---

## 7. NGOÀI PHẠM VI (non-goals)

- ❌ Không đụng `vnbroker/broker/**` (Tier-2, đặt lệnh thật, tiền thật)
- ❌ Không đặt lệnh thật, không gọi write endpoint
- ❌ Không sửa 11 file vượt 800L ngoài `common/data.py` (tách riêng ticket)
- ❌ Không thêm provider mới (chỉ dùng provider đã có)
- ❌ Không xoá `core/exceptions.py` / `adaptive_controller` dù có code chết — là **tài liệu ý định thiết kế**

---

## 8. CÂU HỎI CẦN OWNER TRẢ LỜI (không chặn Wave 1)

| # | Câu hỏi | Chặn cái gì | Nếu chưa trả lời |
|:--|:--|:--|:--|
| ~~**Q1**~~ | ~~Cho phép TCBS/DNSE vào `AUTO`?~~ | — | **Owner ĐÃ TRẢ LỜI 2026-10-10: ĐỒNG Ý.** TCBS/DNSE ổn định, dùng như KBS/VCI. Đã cập nhật `CLAUDE.md:38` |
| **Q2** | `market_cap` ×1000: provider trả **VND** hay **nghìn VND**? Mâu thuẫn nội bộ đã chứng minh, **hướng đúng thì chưa** | W2.4 | Tôi làm W2.1/2/3/5/6, **bỏ W2.4** |
| **Q3** | Có cho phép tôi dùng API key trong `.env` để **probe** (GET-only) để chốt Q2 không? | W2.4 | Ghi `CHƯA CHẠY` |

---

## 9. ROLLBACK

```bash
git revert <commit>          # từng Wave một commit
git revert -m 1 <merge>
```
Mỗi Wave = **một** commit. Không trộn Wave để revert được độc lập.

---

## 10. ĐỊNH NGHĨA XONG

Wave 1+2 xong khi: AC-1..AC-6 xanh **và** `check_all.ps1` exit 0 **và** audit Stage 5
báo **0 blocker + 0 major**. Nếu Q1 chưa được trả lời thì AC-1 chỉ kiểm bằng DNSE,
và điều đó **phải ghi rõ** trong báo cáo — không được báo như đã xong.