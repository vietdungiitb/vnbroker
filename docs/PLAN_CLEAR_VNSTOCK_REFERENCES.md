# KẾ HOẠCH XÓA THAM CHIẾU VNSTOCK — TRIỆT ĐỂ

Trạng thái: `vnbroker` đã hoàn toàn độc lập (codebase viết lại v3.5.0, Direct Provider Architecture). Các tham chiếu còn sót gây hiểu lầm cho người dùng và dev mới.

Mục tiêu: **Xóa sạch, không còn dấu vết** — không chỉ sửa nội dung mà còn sửa cả liên kết tài liệu, tên file, và nhận thức lịch sử.

---

## 1. PHÂN LOẠI CÁC THAM CHIẾU ĐÃ PHÁT HIỆN (38 kết quả `vnstock`)

### 1.1 Tài liệu / URL (ảnh hưởng nhận thức cao nhất)

| File / Vị trí | Nội dung hiện tại | Mức nguy cơ | Đề xuất xử lý |
|---|---|---|---|
| `pyproject.toml:67` | `Documentation = "https://vnstocks.com/docs"` | 🔴 Cao — người dùng mới vào docs sai | Đổi thành URL docs vnbroker (GitHub wiki hoặc `/docs` repo nội bộ) |
| `vnbroker/config.py:78` | `release_url` 3.3.0 trỏ `vnstocks.com` | 🔴 Cao — thông báo nâng cấp sai nguồn | Đổi thành `https://github.com/vietdungiitb/vnbroker/releases/tag/v3.3.0` (như 3.4.0/3.5.0 đã đúng) |
| `CHANGELOG.md:73` | `test_vnstock_client.py` — tên file test đã chết | 🟡 Trung | Xóa dòng này hoặc ghi chú "đã xóa từ v3.1.0" |
| `docs/audit/AUDIT_REPORT_2026-10-01.md` | Toàn bộ §6 "So sánh với vnstock" (259 dòng) | 🟡 Trung — tài liệu audit cũ giữ lại nhưng gây hiểu lầm | Ghi chú header: "§6 — LỊCH SỬ SO SÁNH (không còn áp dụng từ v3.5.0, vnbroker độc lập hoàn toàn)" |
| `docs/COMMERCIAL_SOFTWARE_AUDIT_REPORT.md` | Dòng 322-323: `Thinh Vu` (`support@vnstocks.com`) và `LICENSE.md` liên hệ sai | 🔴 Cao — pháp lý / bản quyền | Sửa lại người liên hệ thành `vietdungiitb@gmail.com` cho khớp `LICENSE.md` |
| `docs/ROADMAP_V33_PLAN.md` | Dòng 7-9: "Cơ sở: vnstock v4... cấm copy code" | 🟡 Trung | Đổi thành "Cơ sở: kiến trúc vnbroker 3.2.0 nội bộ, không phụ thuộc nguồn ngoại" |

### 1.2 Mã nguồn (comment / pattern reference)

| File / Vị trí | Nội dung | Mức nguy cơ | Đề xuất |
|---|---|---|---|
| `vnbroker/common/data.py:753` | `Lọc kwargs theo signature của provider method (pattern vnstock 4.0.4)` | 🟡 Trung — comment gây hiểu lầm code là copy | Đổi thành `(pattern vnbroker v3.5 — lọc kwargs nội bộ)` |

### 1.3 Tài liệu dự án (docs/ — ảnh hưởng nhận thức phát triển)

| File | Tham chiếu chính | Đề xuất |
|---|---|---|
| `docs/audit/AUDIT_REPORT_2026-10-01.md` | §0 nói "là một fork của vnstock"; §6 so sánh tính năng 259 dòng | **Chọn một trong hai:** (A) Xóa §6, sửa §0 thành "vnbroker 3.5.0 — kiến trúc độc lập, không phải fork"; (B) Giữ lại như tài liệu lịch sử nhưng thêm banner "DEPRECATED CONTEXT — không áp dụng" |
| `docs/ROADMAP_V33_PLAN.md` | Dòng 7-8: "Cơ sở: vnstock v4" | Sửa lại nguồn gốc |
| `docs/COMMERCIAL_SOFTWARE_AUDIT_REPORT.md` | Toàn bộ — tài liệu audit cũ (phiên bản 3.1.0) | **Quyết định:** Xóa file này (hoặc đổi tên `ARCHIVED_...`) vì thông tin lỗi thời (phiên bản 3.1.0, không phải 3.5.0) và chứa tham chiếu sai bản quyền |
| `TODO.md:22` | `- [ ] Xóa vnstock references còn sót trong CI/CD workflows` | Đánh dấu hoàn thành hoặc xóa mục này sau khi xử lý xong |

---

## 2. KẾ HOẠCH THỰC HIỆN (3 WAVE — THỨ TỰ CHẶN)

### WAVE 1 — XÓA THAM CHIẾU NGUY HIỂM CAO (P0, ~30 phút)

Mục tiêu: Người dùng mới không còn bị dẫn nhầm.

- [ ] `pyproject.toml` — sửa `Documentation` URL
- [ ] `vnbroker/config.py` — sửa `release_url` 3.3.0
- [ ] `docs/COMMERCIAL_SOFTWARE_AUDIT_REPORT.md` — sửa liên hệ bản quyền (`support@vnstocks.com` → `vietdungiitb@gmail.com`)
- [ ] `vnbroker/common/data.py` — sửa comment dòng 753

### WAVE 2 — SỬA TÀI LIỆU HISTORICAL / ARCHIVE (P1, ~45 phút)

Mục tiêu: Không còn tài liệu gây hiểu lầm cho dev mới.

Quyết định quan trọng cần người dùng xác nhận trước:

> **Q1:** `docs/audit/AUDIT_REPORT_2026-10-01.md` (§6 so sánh vnstock) — **giữ như tài liệu lịch sử (thêm banner)** hay **xóa hoàn toàn §6**?
>
> **Q2:** `docs/COMMERCIAL_SOFTWARE_AUDIT_REPORT.md` (phiên bản 3.1.0, lỗi thời) — **xóa file** hay **đổi tên `ARCHIVED_`**?
>
> **Q3:** `docs/ROADMAP_V33_PLAN.md` — giữ nguyên nội dung lịch sử (chỉ sửa dòng 7-8) hay viết lại hoàn toàn?

### WAVE 3 — KIỂM TRA TRIỆT ĐỂ (P0, ~15 phút)

- [ ] Chạy lại `grep -rni "vnstock" . --exclude-dir=.venv --exclude-dir=build --exclude-dir=dist --exclude-dir=__pycache__`
- [ ] Kiểm tra `grep -rni "vnstocks" .` (domain sai)
- [ ] Kiểm tra `grep -rni "Thinh Vu" .` (tác giả sai)
- [ ] Xác nhận `pyproject.toml` và `config.py` sạch
- [ ] Ghi kết quả vào `TODO.md` (đánh dấu hoàn thành mục 22)

---

## 3. DANH MỤC KIỂM TRA CUỐI CÙNG (CHECKLIST TRIỆT ĐỂ)

- [ ] `pyproject.toml`: không còn `vnstocks.com`
- [ ] `vnbroker/config.py`: `release_url` đúng cho mọi phiên bản
- [ ] `vnbroker/common/data.py`: không còn "pattern vnstock"
- [ ] `docs/audit/AUDIT_REPORT_2026-10-01.md`: có banner hoặc đã xóa §6
- [ ] `docs/COMMERCIAL_SOFTWARE_AUDIT_REPORT.md`: đã xử lý (xóa hoặc sửa bản quyền)
- [ ] `docs/ROADMAP_V33_PLAN.md`: không còn "Cơ sở: vnstock v4"
- [ ] `CHANGELOG.md`: không còn tên file `test_vnstock_client.py` gây hiểu lầm
- [ ] `TODO.md`: mục 22 đã đóng
- [ ] Không còn kết quả `grep -rni "vnstock"` trong mã nguồn chính (`vnbroker/`, `pyproject.toml`, `README.md`)

---

## 4. GHI CHÚ CHO NGƯỜI DÙNG / DEV SAU NÀY

Sau khi hoàn thành kế hoạch này, thêm một dòng vào `README.md` hoặc `CLAUDE.md`:

> `vnbroker` từ v3.5.0 là dự án độc lập hoàn toàn — không phải fork của `vnstock`, không phụ thuộc `vnstock`, không chia sẻ kiến trúc dữ liệu hay bản quyền. Mọi tham chiếu đến `vnstock` trong tài liệu cũ chỉ còn giá trị lịch sử.

---

*Tài liệu lập ngày 2026-10-05. Cần người dùng xác nhận Q1-Q3 ở Wave 2 trước khi tiến hành xóa/sửa tài liệu archive.*
