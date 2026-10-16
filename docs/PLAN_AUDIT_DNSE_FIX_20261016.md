# PLAN_AUDIT: Phân biện Kế hoạch PLAN_DNSE_FIX_20261016

- **Auditor**: subagent độc lập, read-only (không sửa file, không git write, không network)
- **Target Plan**: `docs/PLAN_DNSE_FIX_20261016.md`
- **Verdict**: `NEED_REVISION`
- **Confidence**: `high`
- **Kết quả**: 4 blocker · 7 major · 6 nhỏ

> **Lessons áp dụng: [L-E01, L-E02, L-P04, L-P05]**

## 1. Kết luận & Độ tin cậy

Kiến trúc của plan đúng, đặc biệt hai quyết định khó nhất: **Slice B** (path bug
chứ không phải endpoint vắng → sửa chứ không xoá) và **Slice F** (không bịa enum
`boardId`). Nhưng **không ship được nguyên trạng**:

| Mức | Số | Mã |
|---|---|---|
| Blocker | 4 | B1–B4 |
| Major | 7 | M1–M7 |
| Nhỏ | 6 | N1–N6 |

Điểm đáng chú ý: **lỗi quan trọng nhất nằm ngoài AC**. Slice D + E làm hỏng 7 test
mà bảng Target Files không hề liệt kê. Đây đúng là mẫu lỗi quen của repo này —
số sai trong bản ghi (B1), và việc lớn nhất không nằm trong tiêu chí nghiệm thu.

## 2. Bảng đối chiếu mâu thuẫn

| # | Plan khẳng định | Thực tế | Trích dẫn | Mức |
|---|---|---|---|---|
| B1 | §8: `pytest tests/contract -q` → **72 passed** | **117 passed** (đo lại, exit 0) | plan §8 dòng 2; `docs/CLAIMS.md:292` ghi 117 | 🔴 Blocker — bảng baseline công khai sai, mọi số đếm sau này thừa hưởng con số hỏng. Chính là L-E01 mà plan trích dẫn |
| B2 | Slice E: `position_id` phải là số ⇒ raise trước network | 2 chỗ gọi contract test dùng `position_id="POS1"` ⇒ raise trước ⇒ `capture["url"]` không bao giờ gán ⇒ fail | `tests/contract/test_dnse_endpoint_contract.py:105`, `:130` | 🔴 Blocker — file **không** có trong Target Files |
| B3 | Non-goal #2: guard mới đặt **trước** chỗ gọi `validate_query` ⇒ guard thắng | Test parametrize trên **mọi** method có `market_type`, điền `position_id="x"`, assert `error_code == "INVALID_MARKET_TYPE"` | `tests/unit/connector/dnse/test_market_type_validation.py:160-173` | 🔴 Blocker — 1 test parametrize đỏ |
| B4 | Slice D: "sửa **3** test cũ" | **4** call site trên **4** test; `:310` nằm trong `test_none_of_the_seven_can_reach_the_write_gate` | `tests/.../test_market_data_read_methods.py:159`, `:165`, `:310` | 🔴 Blocker |
| M1 | §5 F: "**26** ứng viên", "**58** request" | 26×3 = 78 ≠ 58; danh sách 26 token nhưng chỉ **24 giá trị khác nhau**; **không có probe nào trong repo** | plan §5 F vs §2.3/§9.5; `scripts/probe_dnse_readonly.py` | 🟡 Major — bảng bằng chứng âm **không tái lập được** |
| M2 | §12: nguồn = `scripts/probe_dnse_readonly.py` | Script **không** probe D1-path/D2/D3/D7/D10/D11; dòng `:103-104` còn khẳng định *"Server không có endpoint working-dates"* — **sai sau Slice B** | `scripts/probe_dnse_readonly.py:86-88`, `:103-104` | 🟡 Major — script tương phản với plan; file lại **untracked** |
| M3 | §4: "`check_lessons` kiểm dòng `Lessons áp dụng` ✓" | Script quét `docs/LESSONS/` (C1 ≤120 dòng, C2 ≤40 lesson, DRIFT vs `INDEX.md`); **không** đọc plan | `scripts/check_lessons.py:43`, `:66-153` | 🟡 Major — plan khẳng định 1 gate kiểm thứ không kiểm |
| M4 | Slice B: "`client.py:666-669` bỏ chỗ gọi `dry_run` trùng" | Chỉ có **một** lượt truyền `dry_run`; facade vẫn đúng ⇒ **task ảo**. Và plan **bỏ sót** việc thật: danh sách key `_to_dataframe` thiếu `workingDates` | `client.py:666-669`, `:72-77` | 🟡 Major |
| M5 | §5 C đổi chữ ký `get_orders` | 2 nơi ghim chữ ký, không có trong Target Files | `docs/DNSE_API_CONTRACT.md:31`; `vnbroker/broker/capabilities.py:162-165` | 🟡 Major — doc drift ngay sau merge; `test_capability_contract.py:72-84` dùng `inspect.signature` nên **không** bắt được drift |
| M6 | Target Files: C = `order_service.py`+`client.py`; E = 3 service+`client.py` | Slice C **chưa** mô tả sửa gì ở `client.py`, mà AC-C1 lại phải đi qua API công khai (`client.py:185-201` không có `page_index`). Slice E **không** cần `client.py` | plan:19-25 vs `client.py:185-201` | 🟡 Major — AC-C1 không thỏa trên bảng Target Files (L-P04) |
| M7 | §2 non-goal #4: "ngoài 2 case ở lát **D và E**" | Lát E tự nói "giữ nguyên chữ ký"; case thứ hai là lát **C** | plan:73-74 vs :232-233 | 🟡 Major — tự phản trong plan |
| N1 | AC-A1, AC-A4 | AC-A1 kiểm helper có thể không có caller; AC-A4 sau khi `get_trades` dùng chung helper thì **tautology** | plan:116-134 | 💭 xanh cả khi lỗi còn |
| N2 | AC-B3, AC-F1, AC-F2 | AC-B3 cần dữ liệu thật (offline không kiểm được); AC-F1 đo production; AC-F2 assert chuỗi docstring | plan:162-164, :279-282 | 💭 phải tách CHƯA CHẠY |
| N3 | Slice A/D: `DNSEValidationError(error_code=...)` | `message` là **positional bắt buộc**; convention hiện có kèm `status_code=400` | `core/errors.py:7-14`; `constants.py:69-77` | 💭 |
| N4 | §6: `client.py` "+10" | Slice A cần docstring đơn vị cho 5 method **mặt tiền** `client.py:438-557` ⇒ 15–25 dòng | plan:291 | 💭 ngân sách thấp |
| N5 | Slice C/D không nhắc facade `Trade` | `Trade.get_orders`/`get_order_history` gọi thẳng `DNSEClient`, **không** forward tham số mới; `trade.py` 1352L bị cấm | `trade.py:1065-1079`, `:1117-1137` | 💭 hệ quả cần ghi |
| N6 | §1: "lát E của **kế hoạch cũ** (dự định **xoá**)" | **Không tìm thấy** tài liệu nào trong repo nói vậy. Tài liệu mới nhất về 2 path này nói **ngược**: *"CHƯA XÁC ĐỊNH ĐƯỢC, KHÔNG ĐƯỢC SỬA VỚI"* | `docs/PLAN_DNSE_API_PARITY.md:71-81`, `:118-120` | 💭 tiền đề "đảo quyết định" không chứng minh được (L-E02) |

## 3. Thẩm định giả định

| # | Giả định | Lệnh | Kết quả thật |
|:--|---|---|---|
| P2 | `get_working_dates` trả `({"dates": []}, None)`, không gọi network | đọc `market_service.py:44-50` | ✅ **Đúng** — `:50`, không có `self._http` trong hàm |
| P3 | `account_service` dùng `/accounts/{a}/corporate-actions` | đọc `account_service.py:56-75` | ✅ **Đúng** — `:72` |
| P4 | Có caller nào phụ thuộc hành vi stub cũ? | `grep` toàn repo | ✅ **KHÔNG có** caller nào trong `vnbroker/` hay `tests/`; chỉ 3 nơi: `client.py:666-669`, `explorer/dnse/quote.py:615-634`, `probe_dnse_readonly.py:105-109`. ⇒ **không vòng nào hỏng** khi trả dữ liệu thật — **và cũng không có test bảo vệ nào** |
| P5 | Có contract/capability test nào nói về 2 method này? | `grep` `tests/contract`, `tests/unit/connector/dnse` | ✅ **Không** |
| P7 | Mọi caller/test của `get_trades_volume_profile` | `grep` toàn repo | 4 call site: `:159`, `:165`, `:171`, **`:310`** ⇒ plan **thiếu `:310`** |
| P8 | Thêm `pageIndex: 1` có làm test đỏ? | đọc 15 file `tests/unit/connector/dnse/` + 9 file `tests/contract/` | ✅ **Không** test DNSE nào assert query dict của `get_orders`; `test_write_gate_layer.py:235` gọi `get_orders("A","STOCK")` nên ổn. Rủi ro duy nhất: sandbox + `tests/integration/test_dnse_integration.py:189-198` ⇒ **CHƯA CHẠY** |
| P9 | Baseline contract | `pytest tests/contract -q` | **117 passed**, exit 0 ⇒ plan §8 dòng 2 **SAI** |
| P10 | Baseline dòng 1 và 3 | `pytest --collect-only` | **2200 collected** / **332 collected**; 2200 = 2174 + 26 module-skip; 2174 + 3 subtest = 2177 ⇒ dòng 1 khớp |
| P11 | `check_lessons` có gì với dòng Lessons? | `scripts/check_lessons.py` | `24/40 lesson - sach`, exit 0 ⇒ **đúng**, nhưng script **không** đọc plan (`grep lesson scripts/` chỉ có `check_all.ps1:104`) |
| P12 | Ngân sách dòng | đọc bằng read tool | client.py **713** · market_service **275** · order_service **166** · account_service **119** · position_service **44** · quote.py **682** · trade.py **1352** ⇒ **7/7 đúng**; không file nào vượt 800L |
| P13 | Bảng ứng viên Slice F tự khớp | đếm token | 26 token, **24 giá trị khác nhau**, 3 endpoint ⇒ 72–78 request ⇒ **"58" không tồn tại** |

## 4. Kiểm tra kỹ thuật

**Trích dẫn: 18/19 đúng.** Sai 1 (`client.py:666-669` — M4), sai 1 về *phạm vi*
(trích dẫn SDK `client.py:236-241`/`:447-451` nằm **ngoài repo**, không commit,
không có sha256 ⇒ **không verify được**), lệch 1 số khống (`:109-119…` là 4 khoảng
cho "5 method").

**Slice B có phải "đảo quyết định" không?** — **Không chứng minh được** (N6).
Không tồn tại tài liệu nào trong repo nói kế hoạch cũ định xoá. Tài liệu mới nhất
(`PLAN_DNSE_API_PARITY.md:71-81`, `:118-120`) nói **ngược**: *"CHƯA XÁC ĐỊNH ĐƯỢC,
KHÔNG ĐƯỢC SỬA VỚI"*. Plan/report/probe đều **untracked**.

**Slice B đúng về hướng** nhưng AC-B2 là **bằng chứng ảo**: AC-B1 kiểm envelope
`url`/`query`, mà `market_service.py:50` trả tuple ⇒ AC-B1 vốn đã FAIL trước khi
sửa ⇒ "đỏ" không chứng minh gì (L-E06).

**Hai hệ quả Slice B plan bỏ sót:**
1. `client.py:72-77` — danh sách key `_to_dataframe` **không có `workingDates`**
   ⇒ `get_working_dates(raw=False)` trả DataFrame **1 dòng** chứa một cell là list.
   Đây mới là thay đổi client-side thật sự.
2. `explorer/dnse/quote.py:622-629` — `quote.working_dates()` sẽ **gọi network thật**
   (nay thì không). Trên sandbox `/market/*` là 404 ⇒ `except Exception` → DataFrame
   rỗng ⇒ an toàn, nhưng **im lặng giống hệt** bug đang sửa (vi phạm đúng L-R01 mà
   lát này sinh ra để chữa).

**Slide F — auditor phản biện đúng, nửa đầu buộc phải nhượng:**
- Với **D10**: server trả 200 khi bỏ `boardId` ⇒ tham số thật sự tuỳ chọn; ghi
  "chưa tài liệu hoá" là đúng.
- Với **D11**: server trả lỗi `oneof` — tức **chính server nói** có một tập giá trị.
  Plan **cắt** body lỗi rồi kết luận "không có giá trị hợp lệ" ⇒ suy đoán.
- **Từ điển sai có thật**: repo **đã** tài liệu hoá `board_id="G1"`
  (`websocket.py:278` ghép `STO.G1`/`DER.G1`; `:19` kênh `top_price.G1.json`), và
  `/instruments` **trả cột `boardId`** (`explorer/dnse/listing.py:29-30`) ⇒ lấy từ
  điển server tự trả về chỉ tốn **1 request**.

## 5. Yêu cầu chỉnh sửa

1. **[B1]** Sửa §8: contract = **117 passed** (exit 0). Đo lại toàn bảng tại commit
   đang làm việc; ghi commit + máy. Không copy `AGENT_PROTOCOL.md`.
2. **[B2]** Thêm `tests/contract/test_dnse_endpoint_contract.py` vào Target Files lát
   E; sửa `position_id="POS1"` → giá trị số hợp lệ. Không đổi *nghĩa* kiểm path.
3. **[B3]** **Chốt thứ tự guard trước khi code**: để `marketType` được kiểm trước
   (khớp `http_client.py:83-90` và test parametrize), `position_id` kiểm sau.
4. **[B4]** Sửa "3 test" thành 4, liệt kê `:158-160`, `:163-166`, `:310`.
5. **[M1]** Rút lại số 26/58 hoặc **thêm probe vào repo** để bảng tái lập được.
6. **[M2]** Thêm `scripts/probe_dnse_readonly.py` vào Target Files; sửa comment
   `:103-104`; bổ sung probe D2/D3/D7/D10/D11; **commit** plan/report/script.
7. **[M3]** Sửa §4: `check_lessons` **không** kiểm dòng `Lessons áp dụng`.
8. **[M4]** Xoá task ảo; thay bằng bổ sung `workingDates` vào key list `_to_dataframe`.
9. **[M5]** Thêm `docs/DNSE_API_CONTRACT.md` + `vnbroker/broker/capabilities.py` vào
   Target Files lát C.
10. **[M6]** Sửa bảng Target Files: lát C **phải** sửa `client.py:185-201`; lát E
    **bỏ** `client.py`.
11. **[M7]** Sửa non-goal #4: "ngoài 2 case ở lát **D và C**".
12. **[N1]** AC-A4 viết lại để **không tautology** (vd: monkeypatch `_history_query`
    và assert nó được gọi bởi cả `get_trades` và `get_quotes`).
13. **[N2]** Tách AC không kiểm offline được sang mục CHƯA CHẠY.
14. **[N3]** Sửa snippet lỗi: `DNSEValidationError(message=..., error_code=...,
    status_code=400)`.
15. **[N4]** Ngân sách `client.py`: +10 → **+25**.
16. **[N5]** Ghi hệ quả lên `Trade` (không forward tham số mới; `trade.py` bị cấm).
17. **[N6]** Bỏ tiền đề "đảo quyết định" hoặc trỏ tới tài liệu cụ thể có commit.

## 6. Kết luận của supervisor (đã tự kiểm chứng, không tin lời subagent)

Supervisor đã **chạy lại** các phép kiểm quan trọng. Kết quả:

| Claim audit | Xác minh |
|---|---|
| B1 contract=117 | ✅ **Đúng** — chạy lại `pytest tests/contract -q` → **117 passed**, exit 0 |
| B2 `position_id="POS1"` | ✅ **Đúng** — đọc `test_dnse_endpoint_contract.py:105`, `:130` |
| B3 test parametrize | ✅ **Đúng** — đọc `test_market_type_validation.py:160-173` |
| B4 `:310` bị bỏ sót | ✅ **Đúng** — đọc `test_market_data_read_methods.py:298-313` |
| M3 `check_lessons` không đọc plan | ✅ **Đúng** — `scripts/check_lessons.py:43` `DEFAULT_DIR = REPO/"docs"/"LESSONS"` |
| M4 `workingDates` thiếu trong key list | ✅ **Đúng** — đọc `client.py:72-77` |
| N3 `message` positional | ✅ **Đúng** — đọc `core/errors.py:7-14` |
| P12 ngân sách dòng | ✅ **Đúng** 7/7 |
| Slice F "G1" là từ điển đáng thử | ✅ **Đúng** — `websocket.py:19`, `:278`; `listing.py:29` |

**Bổ sung do supervisor — mạng đã đổi trạng thái giữa phiên.** Sau khi probe thành
công (D1/D5 có bằng chứng 200), probe tiếp theo lúc ~16:40 gặp TLS handshake timeout
**3/3 lần** (12.5s mỗi lần) — đúng triệu chứng "có VPN" đã ghi ở
`REPORT_DNSE_LIVE_20261016.md` §1. Hệ quả bắt buộc:
- Giả thuyết `boardId = "G1"` / `marketId` kiểu `G*` **chưa kịp thử** ⇒ `CHƯA CHẠY`.
- Cổng re-probe live ở Stage 6 sẽ là **CHƯA CHẠY** trừ khi mạng về.
- Bằng chứng D1/D5 đã thu **vẫn có giá trị** (đo ở đầu phiên, không VPN) nhưng
  phải ghi kèm điều kiện mạng tại thời điểm đo.