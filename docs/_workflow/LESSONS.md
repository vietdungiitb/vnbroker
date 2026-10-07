# Bài học từ quy trình cho dự án vnbroker
# Cập nhật: 2026-10-07 — sau khi sửa cổng G1-G6 thành script thật.

## Bài học 1: Cổng fail-OPEN chỉ có comment sẽ luôn exit 0

Các cổng G1-G6 trước đây chỉ chứa comment `# CHUA CHAY` mà không có lệnh thật.
Với `fail_closed: false`, hook chỉ cảnh báo và cho qua — nghĩa là cổng không chặn gì cả.
**Bằng chứng:** `hermes hooks list` cho thấy 9 hook nhưng không có nào thực thi kiểm tra.

**Cách sửa:** Mỗi cổng phải có script thật (`.sh`) trả về exit 0 (PASS) hoặc exit 1 (FAIL).
Đặc biệt, phải có **ca phủ định** (negative test) chứng minh cổng chặn được — ví dụ,
chạy script với input cố tình sai và xác nhận nó exit 1. Nếu không có ca phủ định,
không thể khẳng định cổng hoạt động.

## Bài học 2: Scaffolding sinh từ template dự án khác mang theo lệnh sai

Khi sinh `docs/_workflow/` từ template dùng chung, các file mang theo tên dự án `eoffice-be`
và lệnh `npm test` — trong khi `vnbroker` là dự án Python dùng `pytest`.
Nếu không `grep` lại sau khi sinh, tài liệu sẽ ghi sai và gây nhầm lẫn.

**Cách sửa:** Sau khi sinh từ template, luôn chạy:
```
grep -rn 'eoffice-be' docs/_workflow/
grep -rn 'npm test' docs/_workflow/
```
và sửa tất cả các tham chiếu sai trước khi commit.

## Bài học 3: Audit agent có thể chết vì vòng lặp và báo số SAI

Trong quá trình audit, agent có thể rơi vào vòng lặp (loop) và báo cáo kết quả không chính xác
— ví dụ, báo `npm test` pass trong khi thực tế lệnh không tồn tại, hoặc báo số lượng file
khác với thực tế. Nếu supervisor tin mà không kiểm lại, sai số sẽ lan ra toàn bộ tài liệu.

**Cách sửa:** Supervisor phải **tự chạy lại mọi phép đo** trước khi tin báo cáo của agent:
- Đếm file: `ls docs/_workflow/ | wc -l`
- Kiểm nội dung: `grep -rn 'eoffice-be' docs/_workflow/`
- Kiểm lệnh: `grep -rn 'npm test' docs/_workflow/`
- Kiểm thư mục: `ls artifacts/`

Không bao giờ tin báo cáo audit mà không có bằng chứng tự chạy.
