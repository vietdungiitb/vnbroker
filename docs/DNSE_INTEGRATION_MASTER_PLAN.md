# DNSE Integration Master Plan

## 1. Scope va ket qua can dat

Scope tich hop DNSE vao vnstock theo huong "API thong nhat, khong hoc lai tu dau".

Ket qua can dat:

- Nguoi dung vnstock co the goi DNSE voi style quen thuoc.
- Team de dang mo rong endpoint DNSE moi ma khong tao fat file.
- Co test strategy ro rang cho unit, integration, E2E.

## 2. Nguyen tac thiet ke

- Tach file theo domain (account, market, order, position, token).
- Giu 1 facade DNSE de nguoi dung public API de nho.
- Giu backward compatibility toi da cho API cu.
- Chuan hoa ten tham so va format du lieu tra ve.
- Fail fast voi loi co nghia, log du thong tin de debug.

## 3. Kien truc tong quan

- Tang Core:
  - Signature/auth.
  - HTTP transport.
  - Error mapping.
  - Config/env.
- Tang Service:
  - AccountService.
  - MarketService.
  - OrderService.
  - PositionService.
  - TokenService.
- Tang Facade:
  - DNSEClient (public entry cho connector).
- Tang Adapter/API:
  - Mapping vao Vnstock/Trading adapter theo style hien co.

## 4. Giai doan trien khai

### Phase 1 - Refactor module (1-2 ngay)

- Tao core + services + facade.
- Muc tieu: khong con business logic trong 1 file lon.

### Phase 2 - Public API thong nhat (1 ngay)

- Mapping method theo naming nhat quan voi vnstock.
- Muc tieu: nguoi dung goi ham de nho, tham so de doan.

### Phase 3 - Backward compatibility (0.5 ngay)

- Giu `trade.py` lam lop wrapper mong.
- Muc tieu: code cu chay duoc, co canh bao migration.

### Phase 4 - Test + docs + examples (1-2 ngay)

- Unit + integration + dry-run E2E.
- Example scripts cho account/market/trade.

## 5. Rui ro va cach kiem soat

- Rui ro: Signature sai lam request 401.
  - Kiem soat: test rieng cho string-to-sign, header format.
- Rui ro: Sai mapping field giua JSON va DataFrame.
  - Kiem soat: contract test cho schema toi thieu.
- Rui ro: Break API cu.
  - Kiem soat: regression test cho method cu.

## 6. Acceptance criteria

- Goi duoc endpoint account/market/order DNSE tu facade moi.
- Dat, sua, huy lenh qua trading token thanh cong o dry-run.
- Test suite DNSE pass theo nguong da xac dinh trong `docs/DNSE_TEST_PLAN.md`.
- Team QA co the tu chay E2E theo `docs/DNSE_E2E_RUNBOOK.md`.
