# VNBroker Project Audit Discussion Document

**Ngày:** 15/06/2026  
**Chủ đề:** Thảo luận và Đánh giá báo cáo `VN_BROKER_PROJECT_AUDIT_REPORT_20260615.md`  
**Người chuẩn bị:** AI Assistant (Antigravity)

---

## 1. Tóm Tắt Tình Hình Hiện Tại

Bản báo cáo kiểm thử ban đầu (`VN_BROKER_PROJECT_AUDIT_REPORT_20260615.md`) cung cấp một góc nhìn tổng quan tốt về các vấn đề namespace (deprecated proxies) và cấu trúc config. Tuy nhiên, qua đối chiếu trực tiếp với codebase và chạy toàn bộ test suite hiện có, chúng tôi phát hiện ra **83 trường hợp kiểm thử bị lỗi (FAILED)** trên tổng số 583 bài test.

Tài liệu này được lập ra nhằm mục đích thảo luận về các vấn đề kỹ thuật cốt lõi (P0/P1) và thống nhất phương án vá lỗi trước khi triển khai các giai đoạn tiếp theo.

---

## 2. Các Chủ Đề Thảo Luận Chính (Key Discussion Points)

### Chủ đề 1: Lệch Chữ Ký Hàm Viết Lệnh (TCBSEquityService Write API)
*   **Vấn đề**: File test `test_order_write_flow.py` và đặc tả `docs/TCBS_BROKER_SPEC.md` yêu cầu các phương thức đặt, sửa, hủy lệnh phải nhận thêm các tham số kiểm soát bảo mật và định danh:
    *   `place_order(...)` yêu cầu `pin_code: str` và `request_id: str`.
    *   `modify_order(...)` và `cancel_order(...)` yêu cầu `request_id: str`.
*   **Thực trạng code**: Trong `vnbroker/broker/tcbs/equity.py`, các tham số này hiện đang bị bỏ trống trong chữ ký hàm triển khai thực tế.
*   **Hệ quả**: Gây ra **81 lỗi test** do lỗi loại đối số `TypeError`.

### Chủ đề 2: Lỗi Hết Hạn Mock Token (Time-Bomb Test Expiry)
*   **Vấn đề**: File kiểm thử `tests/unit/broker/tcbs/test_session_auth.py` có chứa giá trị mock hết hạn cứng là `2026-05-20T18:00:00Z`.
*   **Hệ quả**: Tại thời điểm hiện tại (15/06/2026), giá trị này đã rơi vào quá khứ, khiến session ngay lập tức được coi là hết hạn và làm thất bại test case `test_authenticate_success_sets_session_token`.
*   **Hướng sửa đổi**: Thay thế giá trị cứng bằng thời gian động trong tương lai (ví dụ: `now + 365 days`).

### Chủ đề 3: Sự Cố Ghi Đè Lựa Chọn Nguồn (DNSE Source Override Bug)
*   **Vấn đề**: Lớp `Vnbroker` trong `vnbroker/common/client.py` tự động kích hoạt chế độ Gateway khi khởi tạo. Khi người dùng cố gắng gọi `.stock(..., source="DNSE")` để kết nối trực tiếp với DNSE, hệ thống bỏ qua tham số `source="DNSE"` này do logic điều hướng Gateway đang bị ép buộc.
*   **Hệ quả**: Gây ra lỗi `AssertionError` ở test `test_vnbroker_stock_supports_dnse`.

### Chủ đề 4: Tình Trạng Tệp Tin Screener
*   **Vấn đề**: Báo cáo kiểm thử ghi nhận `api/screener.py` đã bị xóa. Thực tế tệp tin này vẫn tồn tại nguyên vẹn tại `vnbroker/api/screener.py` và có liên kết trực tiếp với explorer của TCBS. Cần thống nhất xem tệp tin này có thực sự cần loại bỏ để tối ưu hóa PAT-only hay giữ lại cho các cấu hình tương thích ngược.

---

## 3. Đề Xuất Phương Án Khắc Phục Chi Tiết

Dưới đây là các bản vá chi tiết bằng mã nguồn để khôi phục trạng thái hoàn toàn xanh lá (Green build) cho dự án:

### Bản Vá 1: Khắc phục Override Nguồn tại [client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/client.py)
Tôn trọng tham số `source` được truyền cục bộ ở method `.stock()` thay vì để logic Gateway ghi đè hoàn toàn:

```diff
# File: vnbroker/common/client.py (Khoảng dòng 257)

-        if self._use_gateway or effective_source.upper() == "GATEWAY":
+        if (self._use_gateway and (source is None or source.upper() == "GATEWAY")) or effective_source.upper() == "GATEWAY":
             return StockComponents(
                 self.symbol,
                 "GATEWAY",
                 show_log=self.show_log,
                 gateway_client=self.gateway_client,
                 gateway_request_func=self._gateway_request,
             )
```

### Bản Vá 2: Đồng Bộ Chữ Ký Phương Thức tại [equity.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/broker/tcbs/equity.py)
Bổ sung đầy đủ các đối số theo đặc tả kiểm thử:

```diff
# File: vnbroker/broker/tcbs/equity.py (Khoảng dòng 270)

     def place_order(
         self,
         account_no: str,
         symbol: str,
         side: str,
         order_type: str,
         quantity: int,
-        price: int,
+        price: float,
+        pin_code: str,
+        request_id: str,
         *,
         dry_run: bool = True,
     ) -> dict:
```

### Bản Vá 3: Động Hóa Thời Gian Mock tại [test_session_auth.py](file:///c:/Mujoco%20Projects/vnbrokder/tests/unit/broker/tcbs/test_session_auth.py)
Tránh việc test bị lỗi khi chạy ở tương lai:

```python
        # File: tests/unit/broker/tcbs/test_session_auth.py (Dòng 158)
        from datetime import datetime, timezone, timedelta
        future_date = (datetime.now(tz=timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_resp.json.return_value = {
            "token": "jwt.real-token",
            "expiredTime": future_date,
        }
```

---

## 4. Các Bước Tiếp Theo Đề Xuất (Next Steps)

1.  **Nhất trí về Chữ Ký Hàm**: Xác nhận xem `pin_code` và `request_id` có cần truyền xuống payload gửi tới TCBS API trong trường hợp `dry_run=False` hay không, hay chỉ cần dùng để validate ở tầng ngoài.
2.  **Thực Hiện Áp Dụng Bản Vá**: Tiến hành áp dụng 3 bản vá lỗi P0 nêu trên để chạy lại kiểm thử đạt tỷ lệ pass 100%.
3.  **Dọn Dẹp Phase 1**: Hợp nhất các tệp tin cấu hình (`pytest.ini`, `.flake8`) vào `pyproject.toml` để làm gọn không gian làm việc.
