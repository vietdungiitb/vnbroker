# Evidence: KBS/VCI `history()` — giá điều chỉnh, không có giá thô

**Ngày đo:** 2026-11-24  
**Branch:** `docs/kbs-vci-raw-price-probe` (base `e996cb4`, `main`)  
**Phạm vi:** `vnbroker/explorer/kbs/quote.py::Quote.history`, `vnbroker/explorer/vci/quote.py::Quote.history`, API công khai của KBS/VCI. Không đụng lane tiền (`broker/`).  
**Trạng thái:** đo lường xong, **BLOCKER** — yêu cầu "thêm tùy chọn lấy giá thô" chưa thi hành được.

## 1. Câu hỏi và câu trả lời đo được

Người dùng báo: KBS/VCI trả giá đã điều chỉnh (do chia tách/cổ tức), thiếu giá thô; muốn thêm tùy chọn `adjusted=False`.  
Câu hỏi then chốt: **cơ chế lấy giá thô có tồn tại trong API của 2 provider không?**

### 1.1 Kết quả chính

| Provider | Endpoint hiện dùng | Giá trả về (ACB 2024-01-02 / 2024-03-29) | Công tắc điều chỉnh | Kết luận |
|---|---|---|---|---|
| VCI | `POST /api/chart/OHLCChart/gap-chart` (`explorer/vci/const.py:3`, gọi ở `explorer/vci/quote.py:299,525`) | close `14452.05` → `17233.61` (có lẻ thập phân, đã điều chỉnh) | payload `adjust/adjusted/isAdjusted/priceType/type/mode/isRaw/chartType` — **đều không đổi kết quả**; query string tương tự — **không đổi**; thử 10 path `raw-chart`, `rawChart`, `normal-chart`, … — **404 hết** | **Không tìm thấy công tắc giá thô** trong phạm vi đã thử |
| KBS | `GET /stocks/{symbol}/data_day` (`explorer/kbs/quote.py:410-416`) | close `17252` (số nguyên, đã làm tròn từ giá điều chỉnh) | `adjust`, `isAdjust`, `adjusted`, `adjustType`, `type`, `priceType` — **mọi biến thể trả y hệt baseline** (cùng SHA-256 fingerprint); suffix `data_day_raw`, `data_day_adjusted`, `data_day_adj`, `historical-quotes` — **404 / lỗi timeFrame** | **Không tìm thấy công tắc giá thô** trong phạm vi đã thử |

### 1.2 Lệnh tái lập (đã chạy trên máy này, Python 3.13.14, không dùng credential)

```
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_adjusted.py
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_adjusted2.py
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_adjusted3.py
```

Output tóm tắt (nguyên văn):

```
=== VCI gap-chart ===      status: 200   first close = 14452.05  (ACB 2024-01-02)
=== VCI raw-chart ===      status: 404   Cannot POST /OHLCChart/raw-chart
=== KBS data_day baseline ===            first = {'t': '2024-03-29 07:00', 'c': 17252, ...}
=== KBS data_day adjust=false ===        first = {'t': '2024-03-29 07:00', 'c': 17252, ...}
=== KBS data_day adjustType=0 ===        fp = bda86d34483a  (y hệt baseline)
=== KBS data_day type=raw ===            fp = bda86d34483a  (y hệt baseline)
```

Payload variants VCI (baseline so với mọi biến thể): `first_c=16810.33`, fingerprint `f6533f21c4e9` — **đều giống hệt**.

## 2. Phân tích

### 2.1 Bằng chứng trong repo

- `docs/AUDIT_HISTORICAL_DATA_SYNC.md:14` ghi nhận "Adjusted vs. Unadjusted Data Gap"; `:28-31` khẳng định VCI dùng `gap-chart` (Adjusted), KBS "Adjusted — no option to toggle".
- `docs/AUDIT_HISTORICAL_DATA_SYNC.md:93` đề xuất `adjusted=False` → `/OHLCChart/raw-chart` cho VCI. **Đề xuất này SAI**: endpoint trả HTTP 404 (đo ở §1.2). Đây là trường hợp L-P06 (AC đòi thứ không tồn tại trong nguồn sự thật).
- `vnbroker/explorer/kbs/const.py:26` có `_SAS_HISTORICAL_QUOTES_URL` nhưng **không được dùng ở đâu** trong code; gọi thử → 404 `No context-path matches the request URI`.
- `vnbroker/api/quote.py:132-172` chuyển tiếp `**kwargs` cho provider, nên thêm tham số ở explorer là đủ về mặt luồng — **không phải** chỗ bị chặn. Chỗ bị chặn là provider không có dữ liệu thô.
- `vnbroker/common/corporate_actions.py:84-118` chỉ trích tỷ lệ chia cổ phiếu thưởng từ tiêu đề sự kiện VCI; **không** có hệ số điều chỉnh giá của provider, nên không thể tự "khử điều chỉnh" chuỗi giá một cách đáng tin cậy từ dữ liệu hiện có.

### 2.2 Root cause

Trong phạm vi API public đã khảo sát, cả hai provider chỉ phục vụ chuỗi giá đã điều chỉnh để vẽ biểu đồ liên tục qua sự kiện quyền; **không tìm thấy** tham số hay endpoint nào trả giá khớp lịch sử chưa điều chỉnh. Đây là kết luận "not found", **không phải** bằng chứng "không tồn tại" (xem §5.1). Audit tháng 7/2026 viết đề xuất `raw-chart` dựa trên phỏng đoán, chưa từng gọi thử endpoint.

### 2.3 Tác động

- Không thể đáp ứng yêu cầu `adjusted=False` cho KBS/VCI bằng cách đổi endpoint/tham số.
- Nếu cứ thêm tham số rồi âm thầm trả giá điều chỉnh, sẽ tạo ra **sai lầm im lặng** (giống bug `match_type` đã ghi trong `CLAUDE.md`): caller tưởng đang dùng giá thô. Phải **fail rõ ràng** hoặc **đổi nguồn**.

## 3. Phương án đề xuất (chưa thực hiện — chờ Owner chọn)

| # | Phương án | Ưu | Nhược | Ưu tiên |
|---|---|---|---|---|
| A | Thêm `adjusted` vào `history()`; với KBS/VCI, `adjusted=False` ném `ProviderBadRequestError` kèm giải thích + link evidence này; `adjusted=True` giữ nguyên hành vi. **Dùng `ProviderBadRequestError`, KHÔNG dùng `NotImplementedError`**: `source_router.should_failover()` trả `False` cho cái trước, `True` cho cái sau (`core/source_router.py:476-479,493`) — cái sau sẽ bị AUTO failover nuốt | API trung thực, fail rõ ràng ở mọi chế độ, có contract test, không bịa endpoint | Vẫn chưa có giá thô | **Cao nhất — đã được Owner chọn 2026-11-24** |
| B | `adjusted=False` → route sang TCBS (OHLC tính từ tick thô, `docs/AUDIT_HISTORICAL_DATA_SYNC.md:30`) | Có giá thô thật | Đổi provider, độ sâu lịch sử kém, cần đo lại; vượt phạm vi "KBS+VCI" | Trung bình |
| C | Tự khử điều chỉnh bằng hệ số từ corporate actions | Giữ provider | Cần hệ số điều chỉnh chính xác từ provider (hiện không có); rủi ro sai số lớn | Thấp — chưa khả thi |
| D | Chỉ cập nhật tài liệu/capability flag, không thêm tham số | Tối giản | Không đáp ứng yêu cầu người dùng | Thấp |

## 4. Kiểm thử / validation sẽ thêm khi triển khai

- Unit test cho 2 explorer: `history(adjusted=True)` → giữ nguyên frame; `history(adjusted=False)` → raise `ProviderBadRequestError` với thông báo có chứa "giá thô"/provider; thêm ca `parallel=True` để chặn nhánh `fetch_multiple` nuốt lỗi.
- Test `api/quote.py`: `@retry` trần (`api/quote.py:123`) phải được filter để lỗi này không bị bọc thành `tenacity.RetryError`.
- ~~Contract test `capabilities()["quote"]["adjusted_modes"]`~~ — **đính chính**: `capabilities()` chỉ tồn tại ở broker lane (`vnbroker/broker/capabilities.py`), không có registry tương đương cho quote tầng 1. Không đưa vào scope; thay bằng unit test trên 2 explorer (xem plan §3 AC-1/2/7/9).
- Gate repo: `pwsh -File scripts/check_all.ps1 -Quick` (không có `.venv` trên máy này — dùng `python -m py_compile` + ruff nếu có, ghi rõ `CHƯA CHẠY` nếu không chạy được).

## 5. Re-probe làm rõ (2026-11-24, vòng 2)

Người dùng phản biện rằng kết luận "chỉ có giá điều chỉnh" nghe vô lý và yêu cầu kiểm tra
lại khả năng **hàm gọi API của ta** không hỗ trợ, chứ không phải provider. Đã dò sâu thêm:

| Nỗ lực | Kết quả đo được |
|---|---|
| VCI 17 path × GET/POST (`raw-chart`, `rawChart`, `RawChart`, `raw`, `chart`, `ohlc`, `normal-chart`, `unadjusted-chart`, `original-chart`, `actual-chart`, `gap-chart-raw`, `raw-gap-chart`, …) | Chỉ `gap-chart` + POST → 200; mọi cái còn lại → **404** |
| VCI 18 biến thể payload (cả số `0/1/2`, `adjustType=NONE/RAW`, `priceType=RAW`, `corpAction=false`, `splitAdjust=false`, `gap=false`, `isRaw=true`) | Fingerprint response **y hệt** baseline `913b191a66ef` |
| VCI `timeFrame=ONE_DAY_RAW` / `ONE_DAY_NO_ADJUST` / `ONE_DAY_ADJUST` / `RAW` | Trả `[]` — không phải giá thô, chỉ là timeFrame không hợp lệ |
| KBS 25 biến thể tham số (`adjust=0..3/true/false`, `isAdjust`, `isAdjusted`, `adjustMode`, `priceType`, `corpAction`, `adj`, `type=raw`, `mode=raw`, …) | Fingerprint full-body **y hệt** baseline `be45a4bdecb9` |
| KBS error message tiết lộ tham số `type` | Giá trị hợp lệ chỉ là `tr, is, ob, card, index, win, vn, trading-result` — **không** có raw/adjusted |
| KBS path/host thay thế (singular `stock/`, `data_day_raw`, `historical-quotes`, SAS host) | 404 / lỗi `timeFrame must be one of ...` |

Lệnh tái lập: `python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_round2.py`
và `python ...\probe_leads.py`.

**Người dùng đã tự xác minh độc lập (2026-11-24): VCI/KBS trả giá điều chỉnh, không phải giá thô.**
Kết luận §1 giữ nguyên trong phạm vi các phép thử trên.

### 5.0 Bằng chứng quyết định từ maintainer của vnstock (repo dòng họ)

Người dùng dẫn `https://github.com/thinh-vu/vnstock/releases`. Đã kiểm tra:

- Mọi tag (`v4.0.4`, `v3.5.0`, `v3.4.0`, `v3.3.0`, `v4.0.9`) của
  `vnstock/explorer/vci/quote.py` đều dùng **y hệt** `chart/OHLCChart/gap-chart` với payload
  `{timeFrame, symbols, to, countBack}` — không có tham số adjust/raw nào.
  Release notes và toàn bộ trang releases: 0 kết quả cho `adjust`, `unadjusted`, `giá thô`, `điều chỉnh`.
- **Issue #129 "Giá cổ phiếu trả về trong quá khứ không chính xác"** —
  https://github.com/thinh-vu/vnstock/issues/129 — maintainer `thinh-vu` trả lời
  (nguyên văn, đã dịch các đoạn chính):

  > "Dữ liệu giá lịch sử mà Vnstock cung cấp là dữ liệu sử dụng cho việc biểu diễn đồ thị
  > kỹ thuật (**giá đã điều chỉnh**) ... Giá mà em đang sử dụng làm tham chiếu là giá trị
  > giao dịch thực tế của cổ phiếu (**chưa điều chỉnh**). Cả 2 dữ liệu này đều đúng ...
  > **Hiện tại Vnstock chỉ cung cấp khả năng truy xuất dữ liệu giá lịch sử này cho nhà
  > tài trợ dự án mà không có sẵn cho bản công khai**."

  ⇒ Kết luận: giá thô **có tồn tại**, nhưng nằm ở **sản phẩm sponsor (`vnstock_data`)**,
  **không có trong API public** mà vnbroker đang gọi. Đây giải thích trực tiếp tại sao mọi
  phép thử endpoint/tham số công khai ở §1 và §5 đều vô hiệu.

Lệnh tái lập (GitHub API, không cần token):
`requests.get("https://api.github.com/repos/thinh-vu/vnstock/issues/129")` + `/comments`.

### 5.1 Câu hỏi mở (đã thu hẹp bởi §5.0)

Người dùng phản biện đúng: provider **có** giá thô, chỉ là ta chưa tìm ra endpoint/API.
§5.0 xác nhận giá thô nằm ở **bản sponsor** (`vnstock_data`). Hướng còn lại cần kiểm tra
là liệu có endpoint public nào khác (ngoài `gap-chart`/`data_day`) trả giá thô hay không —
các phép thử ở §1 và §5 là hữu hạn. Những hướng chưa khảo sát hết:

- JS bundle của web app VCI: chỉ quét được các bundle tĩnh trên trang landing; mã biểu đồ
  có thể nằm trong **chunk tải lười** (webpack dynamic import) chưa được tải/grep.
- API của app mobile / web trading đã đăng nhập (có thể có endpoint riêng, khác host/prefix).
- Dịch vụ SAS nội bộ của KBS: `_SAS_HISTORICAL_QUOTES_URL` (`explorer/kbs/const.py:26`)
  trả 404 với path hiện có — chưa loại trừ path/host đúng khác.
- Tên tham số ngoài tập đã thử, hoặc tham số yêu cầu giá trị đặc biệt/kết hợp với tham số khác.
- Hỏi trực tiếp provider / đọc tài liệu chính thức của họ.

⇒ Trạng thái trung thực: **"giá thô tồn tại ở bản sponsor; chưa tìm thấy trong API public"**.
Không nói "provider không có giá thô" — điều đó đã bị §5.0 bác bỏ. Hệ quả với code: giữ
nguyên thiết kế fail-rõ-ràng của phương án A. Nếu sau này có license sponsor hoặc tìm ra
endpoint public khác, chỉ cần thay nội dung `_require_raw_price_support` trong 2 explorer —
bề mặt tham số `adjusted` đã có sẵn, không phải đổi hợp đồng gọi.

> Ghi chú về một giả định đã bị đính chính trong quá trình điều tra: ban đầu tôi dùng mốc
> "giá thô ACB ~25.000đ" để nhận diện điều chỉnh — mốc này **sai** (nguồn công khai cho thấy
> giá cùng kỳ thấp hơn nhiều). Tuy nhiên điều đó **không làm đổi kết luận**: việc xác định
> giá điều chỉnh dựa trên (a) dạng thập phân của chuỗi VCI, (b) sự vô dụng của mọi tham số
> `adjust*`, và (c) xác minh của người dùng — không dựa trên mốc giá đó.

## 6. Next steps / Owner

- Owner đã chọn phương án **A** (2026-11-24); triển khai xong ở branch
  `feat/kbs-vci-adjusted-param`. Chi tiết: `docs/PLAN_KBS_VCI_ADJUSTED_PARAM_20261124.md`,
  `docs/handoffs/HANDOFF_2026-11-24_KBS_VCI_ADJUSTED.md`.
- Vẫn chưa có giá thô thật; phương án B/C cần Owner duyệt riêng.

## 7. Lessons áp dụng

`Lessons áp dụng: [L-P06, L-E01, L-E06]`

- L-P06: AC "raw-chart" không thi hành được → phải đổi AC, không đổi code cho khớp.
- L-E01: mọi con số ở trên kèm lệnh tái lập và đã chạy ở commit `e996cb4`.
- L-E06: bằng chứng là gọi API thật với input thật (`adjust=false`, path `raw-chart`), không phải assert hình thức.
- L-E06 (bis): phản biện của người dùng dẫn tới vòng dò thứ 2 — phải ghi cả phép thử **âm tính**
  (17 path 404, 25 param y hệt baseline), không chỉ kết quả đầu tiên tìm được.
