# Thiết kế: CafeF làm reference/cross-check layer (không phải provider độc lập)

**Ngày:** 2026-11-24  
**Branch:** `feat/kbs-vci-adjusted-param`  
**Bối cảnh:** sau khi đo `docs/evidence/CAFEF_PROVIDER_FEASIBILITY_20261124.md`, Owner định hướng lại: CafeF nên là **nguồn đối chiếu và bổ sung cho các hạng mục còn thiếu**, không phải provider tầng 1 kiểu KBS/VCI.  
**Lessons áp dụng: [L-E01, L-E06, L-P03, L-P06]**

## 1. Các hạng mục còn thiếu — đo trong code thật

| # | Hạng mục thiếu | Bằng chứng file:line | CafeF có không? |
|---|---|---|---|
| G1 | **Giá thô (raw close)** | `explorer/kbs/quote.py:489-494`, `explorer/vci/quote.py:335-345,554-564` chỉ normalize OHLC từ payload đã điều chỉnh; evidence `KBS_VCI_RAW_PRICE_PROBE_20261124.md` | ✅ `GiaDongCua` |
| G2 | **Giá điều chỉnh độc lập để đối chiếu** | `docs/AUDIT_HISTORICAL_DATA_SYNC.md:65-75` mô tả thuật toán cross-validation nhưng repo **không có** implementation | ✅ `GiaDieuChinh` |
| G3 | **Giá trị khớp lệnh (turnover/value)** | `explorer/kbs/const.py:103-123` có map `tv → total_value`, nhưng standard output ở `kbs/quote.py:463-465` chỉ giữ 6 cột; đo thật `get_all=True` vẫn trả đúng 6 cột (`tests probe_cafef_gaps`) | ✅ `GiaTriKhopLenh` (tỷ VNĐ) |
| G4 | **Put-through (thỏa thuận) volume/value** | `kbs/const.py:114-115` map `ptq/ptv`, nhưng bị strip như G3; VCI không có | ✅ `KLThoaThuan`, `GtThoaThuan` |
| G5 | **Phát hiện rebase giá lịch sử** (corporate action) | `common/corporate_actions.py:157-205` chỉ parse sự kiện VCI; không có bước so sánh chuỗi giá | ✅ so tỷ lệ `close_provider / GiaDieuChinh` |
| G6 | **Hiệu chỉnh quá tay (double-adjust)** | `vninvest/docs/evidence/widget-news-events/TPB_OLD_BARS_ADJUSTMENT_REVERIFY_20261124.md:19` đo `adj_close = close × 0,3085` — vượt quá 3,5 lần | ✅ đối chiếu với CafeF adjusted |

## 2. Nguyên tắc thiết kế (chốt trước, L-P03)

1. **KHÔNG** đăng ký CafeF vào `ProviderRegistry` quote pool, `OPEN_SOURCE_CANDIDATES` hay AUTO failover. Lý do: không có intraday/price_depth, chỉ daily/cổ phiếu, độ sâu từ ~2018 — nếu vào pool sẽ trả dữ liệu sai kỳ vọng cho method khác.
2. **KHÔNG** sửa frame của provider, KHÔNG ghi DB, KHÔNG tự áp adjustment. Reference layer chỉ **đọc + trả báo cáo**.
3. **Opt-in, tường minh**: caller phải gọi riêng; output schema **khác** tier-1 frame để không nhầm (có thêm `close_raw`, `close_adjusted`, `value`, `put_through_*`, `source`, `fetched_at`).
4. Dùng chung hạ tầng có sẵn: `core/utils/client.py::send_request`, `core/utils/transform.py::normalize_price_columns`, `core/utils/normalizer.py` cho phần time/tz khi cần trả frame dạng tier-1.

## 3. Thiết kế đề xuất

```
vnbroker/reference/
├── __init__.py          # export CafefReference
├── const.py             # host/path, field map, đơn vị ×1000 / ×1e9
├── client.py            # fetch JSON (pagination) + XLSX export, date-format guard
├── parser.py            # JSON/XLSX → reference frame (raw + adjusted + extras)
└── reconcile.py         # so sánh provider frame ↔ CafeF, phát hiện rebase/double-adjust
```

API đề xuất (chưa implement):

```python
from vnbroker.reference import CafefReference
ref = CafefReference()

# (1) lấp G1/G3/G4 — trả cả giá thô lẫn giá điều chỉnh + trường bổ sung
df = ref.history("TPB", "2022-01-01", "2022-01-06", to_df=True)
# columns: time, open, high, low, close(=raw), close_raw, close_adjusted,
#          volume, value, put_through_volume, put_through_value, source, fetched_at

# (2) lấp G2/G5/G6 — đối chiếu, không sửa frame
report = ref.reconcile(kbs_frame, symbol="TPB", start="2022-01-01", end="2022-12-31")
# report.ratio_mean, report.ratio_std, report.flagged_dates, report.verdict
```

Gợi ý rule đối chiếu (theo `AUDIT_HISTORICAL_DATA_SYNC.md:70-75`):
- Tính `r_t = close_provider(t) / close_cafef_adjusted(t)` trên các ngày giao thoa.
- Nếu `std(r_t) < 0.5%` và mean ổn định → provider đang trả giá điều chỉnh (xác nhận G2).
- Nếu `r_t` **nhảy** tại một mốc và giữ mức mới → provider vừa rebase do corporate action → cảnh báo full reload.
- **Đừng nhầm 0,39 với double-adjust** (đính chính sau khi đo 120 ngày): `KBS/CafeF_raw = 0,39258 (std 0,00001)` và `CafeF_adj/CafeF_raw = 0,41963 (std 0,00012)` — cả hai đều là **một hệ số duy nhất**, chỉ khác convention (~6,5%). Nếu KBS điều chỉnh hai lần thì `KBS/raw` phải ≈ `0,41963² = 0,176`, nhưng thực tế là `0,393` ⇒ **KHÔNG phải double-adjust**. Double-adjust là hệ số **thứ hai nhân thêm** lên close đã điều chỉnh — đúng cái vninvest làm: `adj_close = close × 0,3085` ⇒ raw × `0,39258 × 0,3085 ≈ 0,121` (khớp 5.159,60 / 42.750 ≈ 0,121). Dấu hiệu nhận diện: **tỷ lệ nằm ngoài khoảng đã hiệu chỉnh của provider**, không phải bản thân con số 0,39.

## 4. Bằng chứng đo được làm nền tảng

| Phép thử | Kết quả |
|---|---|
| Cùng phiên TPB 04/01/2022, volume `11.034.900` ở cả 3 nguồn | CafeF raw `42.750` / adjusted `17.940`; KBS `16.783` (= 0,935 × adjusted) |
| KBS `history(get_all=True)` | vẫn chỉ 6 cột `time,open,high,low,close,volume` → G3/G4 thực sự trống |
| JSON CafeF | `GiaTriKhopLenh=467.26` (467,26 tỷ = 11,03 triệu CP × ~42,75 nghìn) → đơn vị ×1e9 |
| Đo 120 ngày giao thoa TPB 2022 (`probe_double_adjust.py`) | `KBS/CafeF_adj = 0,93552 (std 0,00027)`; `KBS/CafeF_raw = 0,39258 (std 0,00001)`; `CafeF_adj/CafeF_raw = 0,41963`. Tỷ lệ cực kỳ ổn định ⇒ rebase detection bằng ratio là khả thi; KBS **không** double-adjust |
| Hệ số điều chỉnh theo năm (`probe_factor_by_year.py`, TPB) | CafeF `GiaDieuChinh/GiaDongCua`: 2019 `0,2545` → 2020 `0,3107` → 2021/22 `0,4195` → 2023 `0,6483` → 2024 `0,7994` → 2025 `0,8392` → 2026 `1,0`. KBS/CafeF_adj: `0,9365 / 0,9359 / 0,9356 / 0,9359 / 0,9349 / 0,9340` (2019→2024) rồi **`1,0013` ở 2025** |
| Sự kiện quyền VCI TPB 2024-2026 (`api.company.Company(source="VCI", symbol="TPB").corporate_actions()`) | `2024-06-20 DIV 500`, `2024-09-23 ISS 20%`, `2025-05-13 DIV 1.000`, `2025-10-30 ISS 5%`, `2026-10-02 ISS 15% + DIV 500` |
| `tests/contract/test_anonymous_provider_contract.py:26-27` | Hợp đồng tier-1 chỉ 6 cột + tz Asia/Ho_Chi_Minh → reference frame phải **khác** để tránh nhầm |

## 4.1 Vì sao giá điều chỉnh của KBS khác CafeF cùng một ngày?

Không phải lỗi, cũng không phải double-adjust — là **khác tập sự kiện/công thức điều chỉnh**:

- Hệ số điều chỉnh của **chính CafeF thay đổi theo năm** (0,2545 → 1,0): mỗi sự kiện quyền
  mới **rebase lại toàn bộ lịch sử** trước nó. Không có một hệ số "chuẩn" duy nhất.
- KBS và CafeF **đồng ý gần như tuyệt đối ở nến 2025** (`0,84029` vs `0,83918`, tỷ lệ `1,0013`)
  nhưng KBS thấp hơn ~6,5% ở mọi nến **trước 2025** (`KBS/CafeF_adj ≈ 0,934–0,936`).
  Theo danh sự kiện VCI ở bảng trên, các sự kiện nằm giữa 2024-12-29 và 2025-12-30 là
  **`2025-05-13 DIV 1.000 VND`** và **`2025-10-30 ISS 5%`** ⇒ hai bên khác nhau ở cách
  đưa một trong hai (hoặc cả hai) sự kiện 2025 vào hệ số lịch sử. (Chưa xác định được
  sự kiện cụ thể nào — cần đối chiếu thêm với công thức từng bên; tuyệt đối không khẳng định.)
- Loại trừ double-adjust bằng số: nếu KBS nhân hai lần thì `KBS/raw ≈ 0,41963² = 0,176`,
  thực tế `0,39258` (xem §3).

**Hệ quả cho thiết kế reconcile:** so sánh giá điều chỉnh giữa 2 provider bằng equality là
sai; phải dùng **tỷ lệ ổn định + tolerance** (~0,5%), và chỉ báo động khi **tỷ lệ nhảy**
(theo dõi chuỗi tỷ lệ theo thời gian) — chính là tín hiệu rebase cần full reload theo
`docs/AUDIT_HISTORICAL_DATA_SYNC.md:70-75`.

## 5. Việc cần làm & kiểm thử (đề xuất, chưa triển khai)

| Slice | Việc | Test |
|---|---|---|
| R1 | `const.py` + `client.py` + date-format guard (control dates DD/MM reject, mock 2026 reject, swap day/month) | unit no-network + 3 control dates |
| R2 | `parser.py`: JSON + XLSX, unit ×1000/×1e9, golden TPB 2 ngày cả 2 chế độ | golden fixture `tests/fixtures/cafef_tpb_2022.json` |
| R3 | `reconcile.py`: ratio stats + rebase/double-adjust flags | unit với frame giả có rebase chủ động |
| R4 | Facade export (quyết định: standalone import hay `Vnbroker.reference(...)`) | import test từ package root |
| Gate | `check_all.ps1` (hiện **CHƯA CHẠY** — thiếu `.venv`), ruff, pytest contract/full | báo output thật |

## 6. Rủi ro / quyết định Owner

- **ToS & rate-limit** khi tải bulk (vninvest plan §7 cũng bắt chốt) — cần Owner duyệt.
- **openpyxl** đã có trong môi trường (3.1.5); nên khai optional extra trong `pyproject.toml` nếu dùng XLSX — file này là shared, cần coordinator.
- Độ sâu ~2018→nay; không dùng cho backtest trước 2018.
- Bẫy định dạng ngày (`MM/DD/YYYY` request, `DD/MM/YYYY` response) — phải có control test.
- Không thay thế KBS/VCI cho intraday, price_depth, index, derivative.

## 7. Next steps / Owner

- Owner chốt: (a) dùng XLSX hay JSON-only; (b) expose qua standalone import hay `Vnbroker.reference`; (c) có cho phép KBS/VCI `adjusted=False` route sang reference này hay vẫn giữ fail-rõ-ràng.
- Sau khi chốt: lập plan riêng, audit độc lập, khai claim, TDD đỏ-trước, gate, cập nhật CHANGELOG/handoff.
- Tham chiếu chéo: `docs/evidence/CAFEF_PROVIDER_FEASIBILITY_20261124.md` (đo API), repo khác `vninvest/docs/PLAN_CAFEF_OHLC_COC_BACKFILL_FINAL_20261124.md` (đã làm dạng bảng + UI COC).
