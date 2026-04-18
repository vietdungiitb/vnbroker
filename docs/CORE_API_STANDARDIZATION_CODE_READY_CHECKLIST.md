# Code Ready Checklist - Gate trước khi vào coding

> Mục tiêu: Chỉ bắt đầu coding khi tất cả thủ tục đầu vào đã hoàn tất.

---

## A. Business và scope gate

- [ ] Scope đã chốt theo RFC.
- [ ] Danh sách API bắt buộc trong release đã chốt.
- [ ] Out-of-scope đã ghi rõ để tránh trượt phạm vi.

## B. Contract gate

- [ ] Signature hàm đã đóng băng cho sprint hiện tại.
- [ ] Schema chuẩn đã có tài liệu và ví dụ payload.
- [ ] Error code contract đã chốt.
- [ ] Chính sách backward compatibility đã chốt.

## C. Architecture gate

- [ ] Capability matrix cho từng provider đã xác nhận.
- [ ] Thiết kế alias cho method mismatch đã xác nhận.
- [ ] Quy tắc không sửa lõi khi thêm provider mới đã được team đồng thuận.

## D. Delivery gate

- [ ] Task board theo ngày đã phân owner.
- [ ] Ước lượng effort cho từng ticket đã chốt.
- [ ] Critical path đã xác định.
- [ ] Risk register đã cập nhật rủi ro hiện tại.

## E. QA gate

- [ ] Test strategy đã chốt: unit, contract, integration, regression.
- [ ] Acceptance criteria đã chốt.
- [ ] Smoke test sample payload đã sẵn sàng.

## F. Ops gate

- [ ] Branching strategy đã chốt.
- [ ] Merge gate và reviewer matrix đã chốt.
- [ ] Release checklist đã chốt.

## G. Docs/Audit gate

- [ ] Docs index đã cập nhật đủ link tài liệu.
- [ ] Audit file trung tâm đã cập nhật.

---

## Quy tắc GO/NO-GO

- GO: Tất cả mục A-G đều đạt.
- NO-GO: Chỉ cần một mục critical chưa đạt thì chưa vào coding.

Critical items:
- Contract chưa chốt.
- Capability matrix chưa chốt.
- Acceptance criteria chưa chốt.
- Owner ticket chưa phân.
