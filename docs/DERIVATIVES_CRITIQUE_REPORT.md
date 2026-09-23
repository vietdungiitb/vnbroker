# Báo Cáo Phản Biện & Đánh Giá Kế Hoạch Tích Hợp API Phái Sinh (Vietnamese Derivatives APIs)

Báo cáo này tập trung phân tích, đối chiếu ba tài liệu nghiên cứu phái sinh trong thư mục `docs/`:
1. [DERIVATIVES_API_RESEARCH.md](file:///c:/Mujoco Projects/vnbrokder/docs/DERIVATIVES_API_RESEARCH.md)
2. [DERIVATIVES_PUBLISH_RESEARCH_PLAN.md](file:///c:/Mujoco Projects/vnbrokder/docs/DERIVATIVES_PUBLISH_RESEARCH_PLAN.md)
3. [DERIVATIVES_PUBLISH_CRITIQUE_AND_ENHANCEMENT.md](file:///c:/Mujoco Projects/vnbrokder/docs/DERIVATIVES_PUBLISH_CRITIQUE_AND_ENHANCEMENT.md)

Đồng thời, đối chiếu trực tiếp với mã nguồn hiện tại của thư viện `vnbroker` để phát hiện các mâu thuẫn kiến trúc, lỗi logic tiềm ẩn, và đề xuất giải pháp đồng bộ hóa tối ưu.

---

## 1. Đánh Giá Tổng Quan Quan Hệ Giữa 3 Tài Liệu

*   **Tài liệu 1 (API Research):** Cung cấp bức tranh toàn cảnh tốt về các endpoint HTTP thực tế của 4 công ty chứng khoán (TCBS, DNSE, VCI, KBSV). Điểm đáng khen là phân biệt được luồng **Public (Market Data)** và **Private (Trading/Account)**.
*   **Tài liệu 2 (Research Plan):** Định hướng hành động tích hợp dữ liệu phái sinh công khai (Publish APIs). Tài liệu này đã khoanh vùng chính xác các lỗi hiện tại ở phía explorer của DNSE và TCBS.
*   **Tài liệu 3 (Critique & Enhancement):** Đây là tài liệu phản biện xuất sắc và rất chi tiết. Nó đã chỉ ra các khoảng trống lớn của hai tài liệu trước đó như: thiếu cấu trúc mã KRX cụ thể, thiếu số liệu định lượng về độ tin cậy, thiếu Error Handling, và đặc biệt là chỉ ra **sự mâu thuẫn về chiến lược KRX** (dùng feature flag hay auto-convert).

---

## 2. Đối Chiếu Thực Tế Codebase & Phát Hiện Mới (Critical Findings)

Khi đối chiếu các đề xuất trong tài liệu phản biện cũ với mã nguồn thực tế của `vnbroker`, chúng tôi phát hiện một số điểm cốt lõi sau:

### 2.1. Lỗi logic của bộ chuyển đổi KRX (`convert_derivative_symbol`)
Trong [parser.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/core/utils/parser.py#L1112-L1180), hàm `convert_derivative_symbol()` thực hiện parse các ký hiệu phái sinh cũ (như `VN30F2506`) sang mã KRX mới (như `41I1F7000`). Tuy nhiên:
*   **Vấn đề:** Hàm này giả định đầu vào luôn là mã cũ (bắt đầu bằng `VN30`, `VN100`, `GB05`, `GB10`). Nếu đầu vào **đã là mã KRX mới** (ví dụ: `41I1F7000`), hàm sẽ không khớp prefix, đặt `underlying_code = None`, và ném ra lỗi `ValueError("Unknown underlying asset...")`.
*   **Hậu quả:** Caller bắt buộc phải bọc trong block `try-except` (như cách lớp `Quote` của KBS đang làm tại [quote.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/kbs/quote.py#L72-L81)). Đây là một thiết kế phản mẫu (anti-pattern) vì sử dụng Exception để kiểm soát luồng chạy bình thường.
*   **Giải pháp:** Bổ sung bước kiểm tra ở đầu hàm `convert_derivative_symbol()`: nếu mã truyền vào đã khớp với định dạng KRX (`krx_derivative_pattern`), trả về chính nó ngay lập tức.

### 2.2. Sự không nhất quán sâu sắc ở Listing Layer (Series vs DataFrame)
Tài liệu phản biện cũ nhận định TCBS và VCI đang trả về `pd.Series` chứa danh sách mã phái sinh và cần nâng cấp lên `pd.DataFrame`.
*   **Thực tế codebase:** 
    *   `KBSListing.symbols_by_group()` trả về `pd.Series`.
    *   `VCIListing.symbols_by_group()` trả về `pd.Series` (chỉ có cột `symbol`).
    *   `TCBSListing.symbols_by_group()` trả về `pd.Series` (chỉ có cột `symbol`).
    *   `DNSEListing.symbols_by_group()` lại trả về `pd.DataFrame` (chứa đầy đủ thông tin instruments).
*   **Hậu quả:** Vì `BaseAdapter` trong [base.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/base.py) chỉ ủy quyền cuộc gọi trực tiếp đến provider mà không có bước chuẩn hóa kiểu dữ liệu trả về, người dùng cuối khi gọi `Listing().all_future_indices()` sẽ nhận được kết quả có kiểu dữ liệu khác nhau tùy thuộc vào `source` được chọn. Điều này vi phạm nghiêm trọng tính đồng bộ của một SDK.
*   **Giải pháp:** Thống nhất toàn bộ Listing Layer trả về `pd.DataFrame` chuẩn hóa có cấu trúc tối thiểu gồm: `symbol` (chỉ khóa chính), `organ_name` (tên hợp đồng), và `exchange` (sàn giao dịch).

### 2.3. Chưa phân biệt rõ Futures (Hợp đồng tương lai) vs Options (Quyền chọn)
*   **Chi tiết:** Định dạng mã KRX mới có phân biệt:
    *   Bắt đầu bằng `41`: Hợp đồng tương lai (Futures).
    *   Bắt đầu bằng `42`: Hợp đồng quyền chọn (Options).
*   Hàm `convert_derivative_symbol()` hiện tại đang fix cứng prefix trả về là `41` ở dòng 1178 (`f"41{underlying_code}..."`). Do đó, nếu sau này thị trường Việt Nam phát triển thêm các quyền chọn phái sinh chỉ số hoặc trái phiếu chính phủ, logic này sẽ convert sai toàn bộ quyền chọn thành hợp đồng tương lai.
*   **Giải pháp:** Cập nhật hàm convert để nhận diện loại công cụ tài chính (ví dụ dựa vào ký tự trong suffix của mã cũ) để chọn prefix `41` hoặc `42` phù hợp.

### 2.4. Xác thực tham số resolution trong DNSEQuote.history()
Trong [quote.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/dnse/quote.py), API của DNSE hỗ trợ các độ phân giải (`resolution`) gồm `"1"`, `"3"`, `"5"`, `"15"`, `"30"`, `"1h"`, `"1D"`, `"1W"`.
*   Tài liệu phản biện cũ lo ngại rằng DNSE không hỗ trợ đầy đủ các khung thời gian cho phái sinh.
*   **Thực tế:** Cần bổ sung kiểm thử (Smoke test) để xác định xem upstream API `/price/ohlc` của DNSE có chấp nhận lấy dữ liệu nến phút (`1m`, `5m`) cho nhóm phái sinh (khi truyền `type="DERIVATIVE"`) hay không, hay chỉ hỗ trợ khung Daily (`1D`).

---

## 3. Phản Biện Bản Kế Hoạch Triển Khai (Action Plan Critique)

Bản kế hoạch triển khai tại Mục 5 của tài liệu *Critique & Enhancement* rất thực tế, nhưng cần bổ sung các chốt chặn chất lượng (quality gates) dưới đây để đảm bảo an toàn hệ thống:

| Bước | Đề xuất hiện tại | Phản biện & Bổ sung của Antigravity | Độ ưu tiên |
| :--- | :--- | :--- | :--- |
| **1. Smoke Tests** | Gửi request nháp kiểm tra upstream API. | Phải lưu kết quả test vào một file JSON cố định làm dữ liệu tham chiếu (fixtures) phục vụ cho mock tests sau này. | **P0** |
| **2. Sửa DNSE** | Sửa `history()` động hóa `type`, sửa `all_future_indices()`. | Đảm bảo `all_future_indices()` trả về đúng `pd.DataFrame` thay vì `pd.Series` để làm chuẩn hóa cho các bước sau. | **P0** |
| **3. Sửa KRX trên TCBS/VCI** | Kiểm tra tương thích KRX. | Tận dụng cơ chế Feature Flag ở cấu hình chung để cho phép tắt/bật bắt buộc KRX trong trường hợp API của TCBS hoặc VCI chưa cập nhật đồng bộ. | **P1** |
| **4. Chuẩn hóa Schema** | Thiết lập lớp trung gian hoặc chuẩn hóa ở Adapter. | **Quan trọng:** Sửa đổi `BaseAdapter` hoặc viết một wrapper decorator để tự động ép kiểu dữ liệu trả về từ các phương thức Listing thành DataFrame chuẩn, tránh sửa ad-hoc ở từng file provider lẻ tẻ. | **P1** |
| **5. Caching & Rate Limit** | Đề xuất cache dữ liệu tĩnh. | Tích hợp decorator `@cached_listing()` (đã có sẵn trong codebase) vào các phương thức phái sinh mới để giảm tải. | **P2** |

---

## 4. Khuyến Nghị Mã Nguồn Thực Tế (Code-level Recommendations)

### 4.1. Khắc phục lỗi tại `convert_derivative_symbol`
Sửa đổi [parser.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/core/utils/parser.py) để tránh crash khi nhận mã đã convert:

```python
def convert_derivative_symbol(symbol: str, reference_date: date = None) -> str:
    symbol = symbol.upper()
    
    # MỚI: Nếu đã là mã KRX chuẩn thì trả về luôn
    krx_derivative_pattern = re.compile(r'^4[12][A-Z0-9]{2}[0-9A-HJ-NP-TV-W][1-9A-C]\d{3}$')
    if krx_derivative_pattern.match(symbol):
        return symbol
        
    # logic cũ...
```

### 4.2. Khắc phục lỗi hardcode tại `DNSEQuote.history`
Sửa đổi [quote.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/dnse/quote.py#L301-L306):

```python
        # Xác định asset type động
        asset_type = get_asset_type(sym)
        dnse_type = "STOCK"
        if asset_type == "derivative":
            dnse_type = "DERIVATIVE"
        elif asset_type == "index":
            dnse_type = "INDEX"

        query = {
            "type": dnse_type,
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts,
        }
```

### 4.3. Khắc phục lỗi gọi sai endpoint tại `DNSEListing.all_future_indices`
Sửa đổi [listing.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/dnse/listing.py#L229-L231):

```python
    def all_future_indices(self, show_log: Optional[bool] = None) -> pd.DataFrame:
        """Lấy danh sách hợp đồng tương lai phái sinh từ DNSE."""
        df = self._fetch_instruments(security_group_id="DER")
        if show_log or self.show_log:
            logger.info("DNSE all_future_indices: %d hợp đồng", len(df))
        return df.reset_index(drop=True)
```

---

## 5. Kết Luận & Hướng Đi Tiếp Theo

Kế hoạch tích hợp phái sinh hiện tại đã **đầy đủ thông tin về mặt nghiệp vụ**, các phản biện trong tài liệu `DERIVATIVES_PUBLISH_CRITIQUE_AND_ENHANCEMENT.md` rất xác đáng và cần được thực thi. 

**Khuyến nghị bước tiếp theo:** 
1. Người dùng phê duyệt định hướng này.
2. Thực hiện sửa lỗi cục bộ tại DNSE (P0) và nâng cấp logic chuyển đổi symbol KRX (P0).
3. Tiến hành thống nhất cấu trúc dữ liệu trả về (Schema Normalization) ở mức adapter để đảm bảo trải nghiệm đồng nhất trên toàn bộ SDK.
