# PHỤ LỤC B — Đính chính đề xuất (2026-10-11)

Đọc sau Phụ lục A. Mọi mục dưới đây thay thế đoạn tương ứng trong đề xuất gốc [1]
và Phụ lục A [2]. Slice nào dùng số/citation cũ mà chưa đọc file này thì AC vô hiệu.

## B-1. Citation `equity.py:409-441` SAI — mức độ nhẹ hơn đã ghi [L-R06, L-E01]

**Sai:** Phụ lục A §A.1 ghi *"equity.py:409-441 — \_write_request, thiếu 404 và 422"*.

**Đúng (đo ở `main @ 662e2ef`):**

| Dòng | Hàm | Map status | Thiếu |
|:--|:--|:--|:--|
| `broker/tcbs/equity.py:375-441` | `_get` (đường **đọc**) | 401/403/429/400/5xx | 404, 422 — nhưng đây không phải write path |
| `broker/tcbs/equity.py:449-517` | `_write_request` (đường **viết**, dùng cho place/modify/cancel) | 401/403/**422**/429/400/5xx (`:492-497` có 422) | **chỉ 404** |
| `broker/tcbs/_write_http.py:43-87` | `raise_for_status` (chuẩn) | đủ 7 nhánh | — |

**Tái lập:** mở `vnbroker/broker/tcbs/equity.py`, đọc tên hàm ở dòng 375 và 449;
so nhánh `if resp.status_code` hai khối với `_write_http.py:46-87`.

**Hệ quả cho WP-05:** vẫn vi phạm L-R06 (thiếu 404), vẫn sửa bằng cách gọi chung
`raise_for_status` — nhưng AC sửa thành *"thiếu 404"*, không phải *"thiếu 404/422"*.
Bảng 3 write path ở A.1 §A.1 sửa thành: money 7/7, condition_orders 7/7,
equity-write **6/7 (thiếu 404)**.

## B-2. "5/9 method DNSE vi phạm L-R02" là ƯỚC LƯỢNG [L-E01, L-R02]

Đã xác nhận bằng mắt 4 mẫu vi phạm positional (`place_order:351`,
`close_deal:652`, `get_accounts:1014`, `get_balances:1022` — không có `*` trước
`dry_run`), nhưng **tổng 9 chưa được đếm bằng script**. Ghi là **ƯỚC LƯỢNG**
tới khi coordinator chạy:

```powershell
# đếm write method DNSE + kiểm dry_run keyword-only bằng AST, ở đúng commit
.venv\Scripts\python.exe -c "import ast,inspect; ..."
```

và dán output vào đây. AC của WP-13 chỉ khóa sau khi có bảng đo.

## B-3. "17/29 write method ngoài cổng payload" là ƯỚC LƯỢNG [L-E01, L-G02]

Bảng lane ở A.1 §A.1 (tcbs 12 / ssi 5 / dnse 9 / brokerage 3) **chưa được đếm
bằng AST ở commit hiện tại**. Quy tắc L-E01: số trong tài liệu cũ mặc định đã
hỏng. Coordinator chạy lệnh đếm thống nhất (1 định nghĩa write method cho toàn
repo) rồi thay bảng. Tới lúc đó mọi AC của WP-15 dùng số này đều ở trạng thái
**CHƯA KHÓA**.

## B-4. Quy tắc từ nay (đóng L-E01 cho bộ tài liệu này)

Không con số nào được vào AC của slice khi chưa có **1 dòng lệnh + output ở đúng
commit**. Số chưa có lệnh đi kèm phải ghi chữ **ƯỚC LƯỢNG** ngay cạnh số.
