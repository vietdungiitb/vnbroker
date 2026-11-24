# Evidence: CafeF có thể làm provider thay thế KBS/VCI không?

**Ngày đo:** 2026-11-24  
**Branch:** `feat/kbs-vci-adjusted-param`  
**Yêu cầu:** nghiên cứu theo `D:\Mujoco Projects\vninvest\docs\PLAN_CAFEF_OHLC_COC_BACKFILL_FINAL_20261124.md`  
**Kết luận ngắn:** **Có thể bổ sung làm provider tầng 1 cho OHLC ngày (daily), có cả giá thô lẫn giá điều chỉnh — KHÔNG phải thay thế toàn bộ KBS/VCI** (thiếu intraday/price_depth, chỉ số/phái sinh hạn chế).

## 1. Đo lường — endpoint & dữ liệu

Gọi trực tiếp bằng `requests`, **không cần Playwright/cookie** (khác với suy nghĩ ban đầu của plan vninvest):

| Mục | Giá trị đo được |
|---|---|
| JSON | `https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HOSE&Symbol=TPB&StartDate=01/01/2022&EndDate=12/31/2022&PageIndex=1&PageSize=10` → 200, JSON, ~1.5 s |
| Export | `https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistoryExport.ashx?...` → 200, XLSX (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), TPB 2022 = 14.171 byte / 249 dòng / 1,39 s |
| Host | Chỉ `cafef.vn` hoạt động; `s.cafef.vn` + cùng path → 404 |
| Cột XLSX | `Mã, Ngày, Giá đóng cửa, Giá điều chỉnh, Thay đổi, Khối lượng khớp lệnh, Giá trị khớp lệnh, Khối lượng thỏa thuận, Giá trị thỏa thuận, Giá mở cửa, Giá cao nhất, Giá thấp nhất` |
| Field JSON | `Symbol, Ngay, GiaDongCua` (raw close), `GiaDieuChinh` (adjusted close), `GiaMoCua`, `GiaCaoNhat`, `GiaThapNhat`, `KhoiLuongKhopLenh`, `GiaTriKhopLenh`, … |
| Đơn vị | Giá = **nghìn VNĐ** (×1000); `GiaTriKhopLenh` = **tỷ VNĐ** (×1e9) |
| Ngày | **Request `MM/DD/YYYY`**, **response `DD/MM/YYYY`**. Gửi `31/12/2022` → im lặng trả nến 2021 (TotalCount 250) — bẫy đã được plan vninvest ghi nhận |
| Pagination | `PageSize` bị cap ở **30** dù gửi 100/500; `TotalCount` cho biết tổng; `PageIndex` 1-based, page vượt → rỗng |
| Độ sâu lịch sử | TPB: 2016/2017 → 0 dòng; **2018 → 177**, 2019 → 249, 2020+ → 250/năm. Export 2010/2015/2017 → file ~2.333 byte (rỗng). ⇒ **~8 năm, không phải 17 năm** như plan vninvest ghi ở §2 |
| Sàn | `HOSE`, `HNX`, `UPCOM` đều trả dữ liệu với `Symbol=ALL` (JSON TotalCount ln lượt 1592/1316/3421 cho 5 ngày đầu 2024) |
| Chỉ số | `VNINDEX` có dữ liệu (7 dòng/10 ngày); `VN30`, `HNXINDEX` → 0 với `ExchangeType=HOSE` |
| Khung thời gian | Mọi tham số `timeFrame`, `Interval`, `Resolution`, `type=intraday` đều **không đổi** kết quả → **chỉ daily**, không có intraday |
| Dependency | `openpyxl 3.1.5` đã có trong môi trường (pandas 3.0.2) — không cần cài mới |

## 2. Phép thử đối chiếu quyết định (TPB 2022-01-04)

Cùng một phiên, **cùng khối lượng `11.034.900`**:

| Nguồn | close | Ghi chú |
|---|---|---|
| CafeF `GiaDongCua` | **42.750** | giá thô (nghìn VNĐ ×1000) |
| CafeF `GiaDieuChinh` | **17.940** | giá đã điều chỉnh |
| KBS `history()` | **16.783** | ≈ 0,935 × CafeF adjusted → **xác nhận KBS trả giá đã điều chỉnh** |
| VCI `history()` | ~16.x (cùng chiều) | tương tự |

Ngày 05/01/2022: CafeF raw 42.000 / adjusted 17.630; KBS 16.488. Tỷ lệ KBS/CafeF-adjusted ~0,935 nhất quán — khớp với `DB close / CafeF_GiaDieuChinh = 0,932` trong `vninvest/docs/evidence/widget-news-events/TPB_OLD_BARS_ADJUSTMENT_REVERIFY_20261124.md:14`.

⇒ CafeF **giải quyết trực tiếp** yêu cầu gốc của người dùng: có `adjusted=False` (raw) và `adjusted=True` (adjusted) thật, không phải fail-only như thiết kế hiện tại.

## 3. Đánh giá làm provider tầng 1 cho vnbroker

### 3.1 Điểm mạnh
- Có **cả giá thô lẫn giá điều chỉnh** — duy nhất trong các nguồn đã khảo sát làm được điều này.
- Không cần auth/cookie; gọi trực tiếp ổn định (đã đo 200 ở mọi lượt).
- Bulk export rất nhanh: 101.756 dòng/HOSE/2022 trong 2–3 s (theo plan vninvest §2; phép thử TPB 249 dòng = 1,39 s).
- Phủ 3 sàn; schema dễ map sang hợp đồng `tests/contract/test_anonymous_provider_contract.py:26-27` (`time, open, high, low, close, volume`, tz `Asia/Ho_Chi_Minh`).
- `openpyxl` đã có sẵn.

### 3.2 Điểm yếu / rủi ro
| Vấn đề | Tác động |
|---|---|
| Không có `intraday()`, `price_depth()` | Không thay được KBS/VCI ở 2 method này. Có thể follow pattern KBS `price_depth()` (raise `NotImplementedError`) nhưng AUTO router phải không route intraday sang CafeF |
| Chỉ daily; không index/derivative đầy đủ | Phải capability-gate theo symbol type; index chỉ có VNINDEX |
| Độ sâu ~2018→nay | Không thay được KBS/VCI cho backtest dài hơn |
| `PageSize` cap 30, ~1,5 s/request | Single-symbol JSON chậm hơn KBS/VCI; cần pagination hoặc dùng XLSX export |
| Bẫy định dạng ngày MM/DD vs DD/MM | Phải parse/format cẩn thận (đã có 3 control-date test trong plan vninvest C1) |
| ToS / rate-limit tải bulk | Plan vninvest §7 bắt Owner chốt trước; chưa có quyết định |
| Response XLSX | Cần `pandas.read_excel` + openpyxl; tốn RAM hơn JSON |

### 3.3 Kết luận phù hợp
**Không nên "thay thế" KBS/VCI** (word dùng trong câu hỏi), mà nên **thêm CafeF làm provider tầng 1 bổ sung**, chuyên:
- `history(adjusted=True/False)` cho **cổ phiếu, daily** — với `adjusted=False` trả giá thô thật (khác thiết kế fail-only hiện tại).
- Giữ KBS/VCI cho intraday, price_depth, index, derivative và lịch sử trước 2018.

## 4. Đề xuất triển khai (nếu Owner duyệt)

1. `vnbroker/explorer/cafef/{const.py,quote.py}` — `Quote.history(start, end, interval="1D", adjusted=True, ...)`.
2. Fetch: ưu tiên XLSX export (1 request cho cả khoảng); fallback JSON pagination khi cần. Format ngày request `MM/DD/YYYY`, parse response `%d/%m/%Y`.
3. Map: `open/high/low/close` ← `Giá mở/cao/thấp/đóng cửa` (raw) hoặc scale theo `GiaDieuChinh/GiaDongCua` khi `adjusted=True`; `volume` ← `Khối lượng khớp lệnh`; ×1000 cho giá, ×1e9 cho value.
4. `provider='cafef'` đăng ký qua `ProviderRegistry`; thêm vào `OPEN_SOURCE_CANDIDATES` / per-module pool có capability-gate (chỉ `history`, chỉ stock, daily).
5. Contract test: 6 cột chuẩn, tz-aware, lọc biên [start,end], golden TPB 2 ngày với cả 2 chế độ adjusted.
6. Gate: `check_all.ps1` (cần `.venv` — hiện **CHƯA CHẠY**), ruff, pytest contract/full.
7. Quyết định Owner: (a) ToS/rate-limit; (b) có dùng XLSX (openpyxl) hay JSON-only; (c) có thay nội dung `_require_raw_price_support` của KBS/VCI để route sang CafeF khi `adjusted=False` hay không.

## 5. Lệnh tái lập

```
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_cafef_api.py
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_cafef_detail.py
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_cafef_limits.py
PYTHONPATH=D:\Mujoco Projects\vnbroker python ...\probe_cafef_compare.py
```

## 6. Lessons áp dụng

`Lessons áp dụng: [L-E01, L-E06, L-P06]`

- L-E01: mọi con số ở trên có lệnh tái lập; số "17 năm" trong plan vninvest đã bị đo đính chính thành ~2018.
- L-E06: bằng chứng là gọi API thật + đối chiếu cùng volume với KBS/VCI, không phải đọc docs.
- L-P06: AC "route adjusted=False sang nguồn khác" chỉ khả thi sau khi đã chứng minh nguồn đó có giá thô — bây giờ đã có (CafeF).

## 7. Cross-reference

- `docs/evidence/KBS_VCI_RAW_PRICE_PROBE_20261124.md` — tại sao KBS/VCI public không có giá thô.
- `vninvest/docs/PLAN_CAFEF_OHLC_COC_BACKFILL_FINAL_20261124.md` — plan backfill + UI COC (repo khác).
