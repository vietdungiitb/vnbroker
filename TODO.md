# TODO

## vnbroker v3.1.1 — Cleanup Complete (SSI/VNDirect Removal)

### Done
- [x] Xóa MSN explorer (dead code, không có dữ liệu thật)
- [x] Xóa FMP connector (dead code, thiếu API key)
- [x] Xóa file rác (test scratch, benchmark, planning docs, caches)
- [x] Xóa vninvest-sdk (PAT/Gateway architecture đã deprecated)
- [x] Dọn references MSN/FMP khắp codebase
- [x] Sửa 10 test failures do cleanup (4 fixture errors + 6 integration failures)
- [x] Cập nhật README, CHANGELOG
- [x] Xóa SSI brokerage scaffold (`vnbroker/broker/ssi/`)
- [x] Xóa VNDirect brokerage scaffold (`vnbroker/broker/vndirect/`)
- [x] Cập nhật BrokerRegistry chỉ còn TCBS
- [x] Cập nhật README, CLAUDE.md, CHANGELOG, broker/__init__.py

### Future
- [x] Crypto qua Binance spot public (`Vnbroker.crypto()`, v3.4 — xem `artifacts/v3.4-roadmap/04-crypto-fx-worldindex-wiring.md`; riêng `fx()`/`world_index()` vẫn `NotImplementedError`)
- [ ] Bổ sung hỗ trợ FX/World Index qua provider khác (Yahoo, TwelveData, etc. — v3.5)
- [ ] Tăng coverage cho DNSE + broker modules
- [ ] Xóa `vnstock` references còn sót trong CI/CD workflows
- [ ] DNSE brokerage implementation (extend BrokerageBase)
- [ ] Async support cho brokerage write operations
