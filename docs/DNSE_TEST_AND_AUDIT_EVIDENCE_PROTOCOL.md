# DNSE Test and Audit Evidence Protocol

> Mục tiêu: chuẩn hóa cách thu thập minh chứng test và audit cho mọi slice DNSE.
>
> Trạng thái: Protocol
>
> Ngày: 2026-05-08

---

## 1. Nguyên tắc chung

Mọi kết quả `PASS`, `FAIL`, hoặc `SKIP` đều phải có bằng chứng đi kèm.

Không chấp nhận ghi nhận cảm tính hoặc kết luận không có lệnh chạy thực tế.

Một minh chứng hợp lệ phải trả lời được 4 câu hỏi:

- Đã chạy gì?
- Chạy ở đâu?
- Kết quả ra sao?
- Tại sao PASS/FAIL/SKIP?

---

## 2. Ma trận minh chứng bắt buộc

| Lớp kiểm tra | Khi nào cần | Lệnh hoặc nguồn minh chứng | Kết quả tối thiểu |
|---|---|---|---|
| Cấu trúc file | Mỗi slice có file mới hoặc đổi tree | `Test-Path`, `git diff --name-only` | File tồn tại đúng vị trí |
| Integrity diff | Mỗi thay đổi | `git diff --check` | Không có output |
| Unit test | Khi đổi logic hoặc parser | `pytest tests/unit/... -q` | 0 failed |
| Integration test | Khi chạm contract live hoặc env thật | `pytest tests/integration/test_dnse_integration.py -v` | Pass hoặc skip có lý do |
| Smoke/E2E | Khi chạm flow account, market, trade | `tests/examples/dnse_qa_quickcheck` hoặc runbook | Scenario pass/skip rõ ràng |
| Benchmark | Khi chạm path hiệu năng hoặc live contract | Script benchmark hiện hành | Có số liệu và nhận xét |
| Backward compatibility | Khi chạm `trade.py` hoặc public wrapper | Test regression tương ứng | API cũ không gãy |

---

## 3. Chuẩn ghi nhận test evidence

Mỗi slice phải ghi tối thiểu các trường sau trong audit hoặc PR note:

```text
Branch:
Commit:
Slice:
Environment:
Commands run:
Output summary:
Files touched:
PASS/FAIL/SKIP:
Reason or blocker:
Next action:
```

### Quy tắc cho PASS

- PASS chỉ khi output khớp kỳ vọng của slice.
- Với test suite, cần nêu số pass/fail rõ ràng.

### Quy tắc cho SKIP

- SKIP phải nêu lý do môi trường hoặc lý do contract hợp lệ.
- Không được ghi SKIP mơ hồ.

### Quy tắc cho FAIL

- FAIL phải có root cause tóm tắt.
- FAIL phải có hướng xử lý kế tiếp hoặc xác nhận blocker ngoài repo.

---

## 4. Cách gom minh chứng theo loại slice

### 4.1 Slice docs-only

Minh chứng tối thiểu:

- `git diff --check`
- danh sách file đã sửa
- audit entry đã append

### 4.2 Slice code/runtime

Minh chứng tối thiểu:

- `git diff --check`
- unit test hẹp liên quan slice
- integration test nếu chạm contract
- audit entry đã append

### 4.3 Slice market/live contract

Minh chứng tối thiểu:

- unit test hoặc parser test
- live smoke hoặc integration output
- nếu có benchmark thì kèm số liệu trước/sau hoặc baseline

### 4.4 Slice compatibility/regression

Minh chứng tối thiểu:

- test regression dành cho API cũ
- so sánh output shape hoặc behavior
- ghi rõ phần backward-compatible nào đã giữ nguyên

---

## 5. Quan hệ với audit checklist

Protocol này không thay thế [DNSE_AUDIT_CHECKLIST.md](DNSE_AUDIT_CHECKLIST.md).

Nó chỉ quy định cách thu bằng chứng để điền vào checklist đó.

Khi audit:

- checklist trả lời câu hỏi "có đạt hay không";
- protocol này trả lời câu hỏi "bằng chứng ở đâu và ghi thế nào".

---

## 6. Quy tắc append audit

Mỗi slice hoàn tất phải append một block mới vào [docs/CENTRAL_MODIFIED_FILES_AUDIT.md](docs/CENTRAL_MODIFIED_FILES_AUDIT.md) với tối thiểu:

- phạm vi yêu cầu;
- danh sách file đã tạo/chỉnh sửa;
- kết quả kiểm tra;
- ghi chú về skip hoặc blocker nếu có.

Nếu thay đổi là tài liệu mới, phải đồng thời cập nhật [docs/DNSE_INDEX.md](docs/DNSE_INDEX.md) và [module_tree_full.md](module_tree_full.md).

---

## 7. Điều kiện sign-off

Một slice chỉ được sign-off khi:

- minh chứng test đã có;
- audit đã append;
- tree/index đã đồng bộ nếu cần;
- không có `FAIL` chưa giải thích;
- không có secret hay thông tin nhạy cảm trong output.

### Vai trò sign-off

- Developer: xác nhận đã validate slice.
- QA/Reviewer: xác nhận evidence đủ và hợp lệ.
- Tech Lead: xác nhận kết luận cuối cùng và cho phép merge.

---

## 8. Mẫu ghi chú ngắn cho mỗi lần audit

```text
Scope:
Files:
Validation:
Evidence summary:
Result:
Blockers:
Sign-off:
```
