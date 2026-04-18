# PR Checklist - Core API Standardization

> Dùng trực tiếp trong pull request để review nhanh và giảm thiếu sót.

---

## 1) Scope PR

- [ ] PR thuộc một trong các phạm vi: Insider / Financial / Industry / Router / Docs / Tests
- [ ] Không trộn nhiều epic không liên quan trong cùng PR
- [ ] Đã liên kết task ID trong `CORE_API_STANDARDIZATION_TASK_BOARD.md`

---

## 2) Contract compliance

- [ ] Method signature đúng theo RFC
- [ ] Output có đủ cột bắt buộc theo schema chuẩn
- [ ] Có `source` và `source_used`
- [ ] Null-safe cho field provider không trả về

---

## 3) Compatibility

- [ ] Có alias/backward compatibility nếu đổi tên method
- [ ] Có deprecation note nếu cần
- [ ] Không phá API public hiện có ngoài scope được duyệt

---

## 4) Provider extensibility

- [ ] Không hard-code logic đặc thù provider trong code lõi
- [ ] Capability được khai báo đầy đủ
- [ ] Mapping raw -> normalized đặt ở lớp mapping/normalizer

---

## 5) Testing

- [ ] Unit tests mới hoặc cập nhật
- [ ] Contract tests mới hoặc cập nhật
- [ ] Integration smoke test cho source cố định
- [ ] Kiểm thử `source=AUTO` (nếu scope liên quan)
- [ ] Không có test flaky mới

---

## 6) Performance và ổn định

- [ ] Không tạo vòng lặp xử lý row-by-row không cần thiết
- [ ] Ưu tiên vectorized Pandas khi tính benchmark/rank
- [ ] Không tạo thêm bottleneck rõ ràng (I/O lặp, API call dư)

---

## 7) Documentation

- [ ] Cập nhật tài liệu tương ứng trong docs
- [ ] Nếu đổi schema, đã cập nhật JSON schema doc
- [ ] Có ví dụ sử dụng tối thiểu cho API mới

---

## 8) Audit bắt buộc

- [ ] Đã append đầy đủ file thay đổi vào `CENTRAL_MODIFIED_FILES_AUDIT.md`

---

## 9) Merge gate

- [ ] QA approve
- [ ] Tech Lead approve
- [ ] CI pass
- [ ] Không còn TODO critical trong code
