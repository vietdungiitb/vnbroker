# Chuẩn hóa đơn vị giá đa provider (KBS, VCI, TCBS, MSN)

## 1. Mục tiêu

Tài liệu này mô tả cơ chế chuẩn hóa đơn vị giá để mọi nguồn dữ liệu trong vnbroker trả về cùng một định dạng, tránh lỗi lệch đơn vị khi thay đổi provider.

Bài toán điển hình:
- Pipeline A đang lưu giá theo VND tuyệt đối.
- Một số luồng cũ trả về nghìn VND.
- Khi đổi provider, dữ liệu bị lệch hệ số 1000.

## 2. Hành vi mới (an toàn cho production)

vnbroker đã có chuẩn hóa tập trung tại tầng transform.

- Mặc định toàn hệ thống: `VND` (giá tuyệt đối).
- Có thể bật chế độ tương thích ngược: `THOUSAND_VND`.
- Chuẩn hóa áp dụng cho các luồng giá chính:
  - OHLC history
  - intraday khớp lệnh
  - VCI price depth
  - KBS history/intraday path tùy biến

Mỗi DataFrame trả về có metadata:
- `df.attrs['price_unit']`: đơn vị giá sau chuẩn hóa (`VND` hoặc `THOUSAND_VND`).

## 3. Cấu hình nhanh (không cần sửa code)

### 3.1 Mặc định

Không cần cấu hình gì thêm. Nếu không đặt biến môi trường, vnbroker trả giá theo `VND`.

### 3.2 Bật chế độ tương thích ngược (nghìn VND)

Đặt biến môi trường trước khi chạy ứng dụng:

Windows PowerShell:

```powershell
$env:vnbroker_PRICE_UNIT = "THOUSAND_VND"
```

Linux/macOS:

```bash
export vnbroker_PRICE_UNIT=THOUSAND_VND
```

Các giá trị hợp lệ (không phân biệt hoa thường):
- `VND` (mặc định)
- `THOUSAND_VND`
- `THOUSAND`
- `K`

## 4. Hợp đồng dữ liệu cho đội phát triển

Để tránh regression khi thay provider, team backend/data nên chốt contract sau:

1. Tầng ingest luôn lưu giá theo đúng `df.attrs['price_unit']`.
2. Nếu hệ thống downstream yêu cầu cố định VND, chỉ cần assert:
   - `df.attrs['price_unit'] == 'VND'`
3. Nếu phát hiện nguồn dữ liệu bất thường, log kèm:
   - provider
   - symbol
   - interval
   - `price_unit`

## 5. Tích hợp vào dự án hiện có với thay đổi tối thiểu

Nếu code hiện tại đã gọi `Quote(...).history()` hoặc `intraday()`, thông thường không cần sửa.

Mặc định sau khi nâng cấp vnbroker:
- Dữ liệu giá được chuẩn hóa về `VND`.
- Việc đổi `source` giữa `KBS`, `VCI`, `TCBS` sẽ không làm đổi thang đo giá.
- Consumer chỉ cần đọc `df.attrs['price_unit']` nếu muốn kiểm soát chặt contract.

Khuyến nghị thêm đúng 1 lớp bảo vệ ở nơi save DB:

```python
if df.attrs.get("price_unit") != "VND":
    raise ValueError("Unexpected unit before persistence")
```

Nếu muốn chấp nhận cả hai đơn vị trong giai đoạn chuyển đổi:

```python
unit = df.attrs.get("price_unit", "VND")
if unit == "THOUSAND_VND":
    price_cols = [c for c in ["open", "high", "low", "close", "price"] if c in df.columns]
    df[price_cols] = df[price_cols] * 1000
```

## 6. Checklist rollout production

1. Chọn chuẩn chính thức (`VND` khuyến nghị).
2. Thiết lập biến môi trường tại scheduler/worker/webapp.
3. Chạy smoke test với 2 provider (ví dụ KBS và VCI) cùng symbol, cùng ngày.
4. So sánh giá đóng cửa sau chuẩn hóa, sai số cho phép nhỏ theo số chữ số thập phân.
5. Bật cảnh báo nếu `price_unit` khác mong muốn.

## 7. Test regression đã thêm trong repo

Đã bổ sung test đơn vị tại:
- `tests/unit/core/test_price_unit_normalization.py`

Các case chính:
- Mặc định trả `VND`.
- Bật `THOUSAND_VND` cho chế độ legacy.
- Intraday VCI chuẩn hóa đồng nhất.

## 8. Câu hỏi thường gặp

### Q1: Vì sao chọn mặc định VND?

VND tuyệt đối giúp giảm nhầm lẫn khi lưu trữ, tính PnL và hợp nhất nhiều nguồn dữ liệu.

### Q2: Tôi đang có dữ liệu cũ theo nghìn VND thì sao?

Giữ `vnbroker_PRICE_UNIT=THOUSAND_VND` tạm thời để tương thích. Sau đó migration dần bằng phép nhân 1000 trước khi hợp nhất dữ liệu lịch sử.

### Q3: Có cần chỉnh từng hàm ở dự án gọi vnbroker không?

Không bắt buộc. Cấu hình bằng biến môi trường là đủ cho hầu hết trường hợp.

## 9. Tệp mã liên quan

- `vnbroker/core/utils/transform.py`
- `vnbroker/explorer/kbs/quote.py`
- `vnbroker/explorer/vci/quote.py`
- `tests/unit/core/test_price_unit_normalization.py`
