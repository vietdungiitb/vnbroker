# DNSE Implementation Workflow (Dev Playbook)

## 1. Ke hoach giao viec theo ticket

### Ticket DNSE-01: Core foundation

Output:

- Tao `core/config.py`, `core/errors.py`, `core/signature.py`, `core/http_client.py`.
- Unit tests cho signature va error mapping.

Checklist:

- [ ] Signature header dung format.
- [ ] Co nonce support (neu bat).
- [ ] Retry/timeout theo config.

### Ticket DNSE-02: Services layer

Output:

- Tao 5 service files trong `services/`.
- Moi service chi chua endpoint cung domain.

Checklist:

- [ ] Account endpoints day du.
- [ ] Order endpoints day du.
- [ ] Market endpoints day du.
- [ ] Position + close position co san.
- [ ] OTP + trading token flow co san.

### Ticket DNSE-03: Facade client

Output:

- Tao `connector/dnse/client.py`.
- Expose contract methods theo `docs/DNSE_API_CONTRACT.md`.

Checklist:

- [ ] Method names dung contract.
- [ ] raw/DataFrame mode hoat dong dung.
- [ ] Docstring day du params va vi du ngan.

### Ticket DNSE-04: Compatibility

Output:

- Refactor `connector/dnse/trade.py` thanh wrapper mong.

Checklist:

- [ ] API cu khong bi break.
- [ ] Co warning migration.

### Ticket DNSE-05: Tests + docs + examples

Output:

- Test files + scripts demo + cap nhat docs.

Checklist:

- [ ] Unit tests pass.
- [ ] Integration tests pass (hoac co report skipped reason).
- [ ] E2E dry run pass.

## 2. Nhanh branch va quy trinh merge

- Lam viec tren branch `dev`.
- Moi ticket = 1 pull request nho.
- PR phai kem:
  - Summary.
  - Test evidence.
  - Risk + rollback note.

## 3. Coding standards

- Type hints day du.
- Khong duplicate code build request.
- Khong hardcode secret trong source.
- Dat timeout mac dinh va cho phep override.

## 4. Review checklist cho reviewer

- [ ] Co tach module dung blueprint.
- [ ] Public API nhat quan voi vnbroker.
- [ ] Error handling ro rang, khong nuot loi.
- [ ] Test co bao edge cases quan trong.
- [ ] Tai lieu du de QA chay doc lap.
