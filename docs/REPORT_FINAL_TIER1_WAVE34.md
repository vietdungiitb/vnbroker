# REPORT FINAL — Tier-1 Wave 3 + Wave 4

**Ngày:** 2026-10-10 · **Cây:** `main` ← `feat/w34-ratelimit` + `feat/w34-logger`
**Kế hoạch:** `docs/PLAN_TIER1_WAVE34.md` (qua 2 vòng audit)
**Audit:** `docs/AUDIT_TIER1_WAVE34.md` — 0 blocker · 0 major · `confidence: high`
**Cổng:** `docs/TEST_REPORT_TIER1_WAVE34.md` — `check_all.ps1` **exit 0**
**Bàn giao:** `docs/HANDOFF_TIER1_WAVE34.md`
**Lessons áp dụng:** L-E01 L-E02 L-E03 L-E04 L-E06 L-E07 L-P01 L-P02 L-P03 L-P04 L-P05 L-P06 L-R01 L-R03 L-R07

---

## 1. Đã làm gì

Đóng **Wave 3** (rate-limit thật) và **Wave 4** (logger không rò token) — hai việc
cha đã giao nhưng đợt trước để dở.

**Hai blocker do audit bắt, không phải do tôi tự thấy:**

1. **Vòng 1:** kế hoạch định dùng `RateLimitError` sẵn có. Đo thì ra
   `should_failover(RateLimitError(...)) == False` vì nó không có `OSError` trong
   MRO — thay class là **làm AUTO failover chết**, tệ hơn trạng thái trước đợt.
   Sửa: cho nó kế thừa thêm `ConnectionError`.
2. **Vòng 2:** chính tôi đã viết AC trên **đường dẫn sai** — kết luận
   `common.data.Quote` không retry 429 bằng cách soi `hasattr(…,'retry')`. Nhưng
   retry nằm **bên trong** `_run_with_failover`. Đo lại: **3** và **6** attempt.
   Sửa: đưa `common/data.py` (đường người dùng **thật**) vào lát W3.

Hai blocker này đều là loại **chỉ chạy code mới biết**: class trông đúng, hàm
trông đúng, hợp đồng là `isinstance` chứ không phải so chuỗi.

---

## 2. Kết quả đo được

| Chỉ số | Trước `4cd0f2d` | Sau |
|:--|:--|:--|
| 429, source cố định — số HTTP attempt | **3** | **1** |
| 429, AUTO 2 provider — số HTTP attempt | **6** | **2** |
| `should_failover(RateLimitError(...))` | **False** | **True** |
| cooldown với `Retry-After: 120` | **4.935s** | **119.93s** |
| rò token trên 10 chuỗi log thử | **4/10** | **0/10** |
| bóp méo trên 6 chuỗi phải giữ | **1/6** | **0/6** |
| `log.info("%s", dict)` | **mất dòng log** | in đúng |
| `pytest tests/ -q` | 1978 passed | **2032 passed** |

Cổng: **exit 0** · 9 PASS · 1 KNOWN-RED · contract **91** · mypy **1138** (không
lỗi mới) · ruff **0** · version-sync **3.7.0**.

---

## 3. Waiver

| # | Nội dung | Ai quyết | Lý do | Rủi ro còn lại |
|:--|:--|:--|:--|:--|
| **W-1** | `ruff-tests-all` **KNOWN-RED**, 13 lỗi F401/F841 | Coordinator | Có sẵn ở `9d5db1d`, **không do đợt này**; tách riêng (N3) | Không ảnh hưởng `vnbroker/` |
| **W-2** | `Bearer <token ≤15 ký tự>` **không** còn bị che | Coordinator | **Đánh đổi L-R07**: bắt nó sẽ phá prose (`'bearer of the bond coupon'` → `'Bearer ***REDACTED*** the bond coupon'`). Đo được cả hai chiều | Token bearer ngắn lọt log. Đã ghi trong `logger.py` + `CHANGELOG.md` |
| **W-3** | `common/data.py` giữ nguyên **1823 dòng** (đã vượt ngân sách 800L) | Coordinator | Tách file là lát riêng (N2). Lát này **không** làm nó dài thêm — có kiểm bằng lệnh | Vẫn vượt ngân sách |
| **W-4** | 36 `@retry` trong `api/*.py` giữ nguyên (N1) | Coordinator | Sửa 36 chỗ đổi hành vi lỗi cho **mọi** module | Người dùng vẫn nhận `tenacity.RetryError`; `should_failover(RetryError)` chỉ **tình cờ** `True` |

---

## 4. Câu hỏi Owner đã trả lời

| # | Câu hỏi | Quyết định | Trạng thái |
|:--|:--|:--|:--|
| **B1** | TCBS `intraday` không có side (server trả `"a": ""`) | **Loại khỏi AUTO** | ⛔ **Chưa làm** — `supports` là danh sách **module**, `intraday` là **method** ⇒ cần bảng loại theo method + quy tắc C6. Nợ N8 |
| **A1** | `.env` tự nạp | **Opt-in qua env flag** | ⛔ Chưa làm — cần `python-dotenv` hoặc bộ đọc tay. Nợ N7 |
| **A2** | Đo benchmark để quyết thứ tự `AUTO`? | **Có, đo rồi mới quyết** | ⛔ Chưa đo. Giữ nguyên "nối cuối" là quyết định có chủ ý |

---

## 5. Điều CHƯA làm (nói thẳng)

| Việc | Vì sao |
|:--|:--|
| Loại `intraday` TCBS khỏi `AUTO` (B1) | Owner **đã chọn** nhưng cần bảng loại theo **method** + quy tắc cổng C6; làm vội sẽ sửa `supports` (theo **module**) — sai tầng. Nợ N8 |
| `.env` opt-in (A1) | Thêm phụ thuộc là quyết định riêng. Nợ N7 |
| Benchmark p99 (A2) | Chưa có số đo ⇒ không ai lên đầu `AUTO` |
| 36 `@retry` không `reraise` (N1) | Ngoài phạm vi |
| 10 file >800L (N2) · 13 lỗi ruff tests (N3) · mypy 1138 (N4) | Owner không chọn |
| `broker/ssi/auth.py` không qua `SensitiveDataFilter` (N12) | Lane tiền thật — **gợi ý lát kế tiếp** |
| Sửa DNSE (B2) | TLS handshake `openapi.dnse.com.vn` **timeout** từ máy này — tầng mạng, không sửa được bằng code |

---

## 6. Trạng thái CI — đọc trước khi tin badge

**GitHub Actions của repo này KHÔNG chạy.** Job bị từ chối khởi động do billing.
Lần chạy thành công cuối: **2026-10-02**. Mọi gate trong báo cáo này chạy
**LOCAL** qua `scripts/check_all.ps1`, và script in rõ điều đó ở cuối mỗi lần
chạy.

⚠ `mypy vnbroker --strict` **không** phải gate — `--strict` là no-op (1207 lỗi
có sẵn, y hệt `mypy vnbroker`). Gate thật là `scripts/check_mypy_baseline.py`.

---

## 7. Bài học quy trình của đợt này

Ba điều đáng giữ lại, đều đã viết vào `docs/HANDOFF_TIER1_WAVE34.md` §5:

1. **`hasattr` trả kết quả đúng vẫn có thể dẫn tới kết luận sai.** Tôi kiểm
   `hasattr(Quote.history,'retry')` → `False` rồi kết luận "không retry". Phải
   **đếm cái mà AC nói tới**, không kiểm cấu trúc rồi suy hành vi.
2. **Mọi số trong tài liệu cũ đều phải đo lại.** Đợt này đúng 3 con số: 11 file
   (thực 10) · 75 call site (thực 58, và 75 là đếm chuỗi thô) · 15 test (thực 0).
3. **Đếm bằng PowerShell cho số sai.** `Measure-Object -Line` cho 1583 dòng với
   `common/data.py`; `len(splitlines())` cho **1823**.