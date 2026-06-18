# TODO

## vnbroker v3.1.0 — Cleanup Complete

### Done
- [x] Xóa MSN explorer (dead code, không có dữ liệu thật)
- [x] Xóa FMP connector (dead code, thiếu API key)
- [x] Xóa file rác (test scratch, benchmark, planning docs, caches)
- [x] Xóa vninvest-sdk (PAT/Gateway architecture đã deprecated)
- [x] Dọn references MSN/FMP khắp codebase
- [x] Sửa 10 test failures do cleanup (4 fixture errors + 6 integration failures)
- [x] Cập nhật README, CHANGELOG

### Future
- [ ] Bổ sung hỗ trợ FX/Crypto/World Index qua provider khác (KBS, VCI)
- [ ] Tăng coverage cho DNSE + broker modules
- [ ] Xóa `vnstock` references còn sót trong CI/CD workflows
