# AGENT_PROTOCOL — vnbroker

Giao thức chạy multi-agent cho repo này. Skill `multi-agent-workflow` là mặc định
chung; **file này ghi đè** mọi chỗ mặc định không khớp với vnbroker.

> **Lessons áp dụng: [L-E02, L-E07, L-P01, L-P03, L-P04, L-P06]**

## 0. Vì sao file này tồn tại

Skill nói: "Always check the repo first. The skill's per-repo table is a starting
default; `docs/AGENT_PROTOCOL.md` overrides it." Trước 2026-10-16 repo này **không
có** file đó, nên mọi đợt trước phải suy ra gate từ `CLAUDE.md`. Ba sai lệch suy
ra đã tốn công thật:

| Suy ra sai | Thực tế | Hậu quả |
|---|---|---|
| Base branch = `dev` | `dev` đứng ở `6ca4495` (v3.6.0), **cũ hơn `main`**; HEAD khi đó đã 10 commit trên `main` | Đợt mới sửa trên nhánh không ai nhìn thấy |
| Gate = `mypy --strict` | `strict=true` trong `[[tool.mypy.overrides]]` bị mypy nâng thành global ⇒ `--strict` là **no-op**, cả hai đều 1207 lỗi | Báo cáo ghi "strict PASS" là bịa |
| `pytest tests/unit` là gate | Contract test nằm ngoài `tests/unit` | Contract regression lọt |
| Cổng `lessons` kiểm dòng `Lessons áp dụng` trong plan | **Không kiểm.** `scripts/check_lessons.py:43` chỉ quét `docs/LESSONS/` (C1 ≤120 dòng/file, C2 ≤40 lesson, DRIFT vs `INDEX.md`) | Tưởng có gate, thật ra dòng Lessons là **quy ước tự nguyện** |
| Số test lấy từ `CLAUDE.md` | `CLAUDE.md` ghi "1414 passed, 30 skipped" và "contract 72" — đều **cũ** | Đợt 2026-10-16 đã chép cả hai vào `docs/AGENT_PROTOCOL.md`; audit phát hiện, đo lại thành 2177 / 117 |

## 1. Cổng (gate) — chạy 1 lệnh, đừng đọc CI

```bash
pwsh -File scripts/check_all.ps1            # tất cả, ~4 phút
pwsh -File scripts/check_all.ps1 -Quick     # bỏ pytest-full (~40 giây)
pwsh -File scripts/check_all.ps1 -SelfTest  # chứng minh script FAIL khi gate đỏ
```

Exit **0** = sạch · **1** = có gate đỏ thật · **2** = gate **không chạy được**
(thiếu tool/môi trường) — 2 không phải xanh.

Danh sách gate trong `scripts/check_all.ps1:100-112`:

| Gate | Lệnh | Ý nghĩa khi đỏ |
|---|---|---|
| `ruff-src` | `ruff check vnbroker scripts tests/unit tests/contract` | code + script + test mới viết có lỗi |
| `ruff-tests-all` | `ruff check tests` | **KNOWN-RED 13 lỗi** — chỉ đòi *không tăng* |
| `version-sync` | `scripts/check_version_sync.py` | lệch version giữa `pyproject.toml` ↔ docs |
| `lessons` | `scripts/check_lessons.py` | plan thiếu dòng `Lessons áp dụng` |
| `tcbs-coverage` | `scripts/verify_tcbs_coverage.py` | spec TCBS lệch code |
| `tcbs-bodies` | `scripts/check_tcbs_bodies.py` | lệch payload write TCBS |
| `provider-consistency` | `scripts/check_provider_consistency.py` | registry vs `SUPPORTED_SOURCES` lệch |
| `mypy-baseline` | `scripts/check_mypy_baseline.py` | **chỉ fail lỗi MỚI**, không fail số tuyệt đối |
| `pytest-contract` | `pytest tests/contract -q` | hợp đồng provider vỡ |
| `pytest-full` | `pytest tests/ -q --timeout=300` | (bỏ qua khi `-Quick`) |

> ⚠ **CI GitHub Actions của repo KHÔNG chạy** — job bị từ chối khởi động do
> billing. **Badge CI không phải bằng chứng.** Lần chạy thành công cuối 2026-10-02.
> Chạy `check_all.ps1`.

## 2. Bảng chân lý của repo (đo 2026-10-16, không đoán)

Tại `main @ fe76670` + HEAD 10 commit (`f6cf68b`):

| Lệnh | Kết quả | Exit |
|---|---|---|
| `pytest tests/ -q --timeout=300` | 2177 passed, 26 skipped, 3 subtests (187s) | 0 |
| `pytest tests/contract -q` | **117 passed** (66s) | 0 |
| `pytest tests/unit/connector/dnse tests/contract -q` | 332 passed | 0 |
| `ruff check vnbroker tests/unit tests/contract` | All checks passed | 0 |
| `ruff check tests` | **13 lỗi KNOWN-RED** | 1 |
| `mypy vnbroker` | ~1138 lỗi (baseline 1266) — **không phải gate** | 1 |
| `scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1138)` | 0 |
| `scripts/check_lessons.py` | 24/40 lesson đọc | 0 |

**Hệ quả bắt buộc:**
- `mypy vnbroker --strict` **không được ghi là PASS** — nó là no-op (CLAUDE.md §Gates).
- `ruff check tests` exit 1 là hợp lệ; **đòi số lỗi không tăng**, không đòi xanh.
- `CLAUDE.md` ghi "1414 passed, 30 skipped" là **số cũ**; con số ở bảng trên mới hơn.

## 3. Nhánh

| Việc | Dùng |
|---|---|
| Base/integration | `main` (`origin/main`) — **không phải `dev`** |
| Nhánh tính năng | `feat/<ten-nhanh>` tách từ HEAD đang có việc chưa merge |
| Worktree | chỉ khi chạy song song; xem §4 |

`dev` tồn tại nhưng **đứng yên ở v3.6.0**. Trước khi chọn base, kiểm:

```bash
git rev-list --count main..HEAD     # HEAD có đi trước main không
git log --oneline main -5
```

## 4. Mode A hay Mode B

Mặc định **Mode B (tuần tự)**. Sang Mode A (song song) **chỉ** khi tập file của các
worker **rời nhau tuyệt đối** — kiểm bằng script, không bằng mắt:

```bash
node <skill>/scripts/check-overlap.cjs --file docs/CLAIMS.md
```

Lịch sử repo cho thấy cả hai vế đều đúng: đợt HANG1 (Mode A, 4 worker, file
rời nhau) sạch; đợt WAVE 3+4 cần cảnh báo rõ rằng `common/data.py` là **đường
người dùng thật** và đang ở sát trần 800L.

## 5. Deny list — không agent nào tự ý sửa

| File | Lý do |
|---|---|
| `vnbroker/connector/dnse/core/http_client.py` | write gate là **choke point duy nhất**; sửa ở đây là sửa hàng rào tiền thật (money lane) |
| `vnbroker/broker/security/**` | redaction khoá |
| `CLAUDE.md` | coordinator giữ |
| `docs/CLAIMS.md`, `CHANGELOG.md` | coordinator duy nhất |
| `docs/tcbs_body_baseline.json` | baseline của cổng `tcbs-bodies` |
| file > 800L | sửa phải **tách file trước**, không dài thêm (L-P03) |

## 6. Ledger (sổ cái bắt buộc)

`CHANGELOG.md` — mỗi đợt có một mục: phạm vi, delta dòng, rationale, reviewer.
Không có ledger entry = đợt đó chưa xong, dù code đẹp.

## 7. Lessons trong plan — quy ước, KHÔNG phải gate

Mọi plan nên có một dòng:

```
Lessons áp dụng: [L-...]      # hoặc: NONE - <lý do>
```

⚠ **Không có script nào kiểm dòng này.** `scripts/check_lessons.py` chỉ quét
`docs/LESSONS/` (`scripts/check_lessons.py:43`, `:66-153`): mỗi file ≤120 dòng
(C1), tổng ≤40 lesson (C2), `INDEX.md` khai báo đúng tổng + trỏ hết file. Cổng
`lessons` gọi nó, nhưng **không** đọc file plan. Đây là quy ước của repo, không
phải cổng chặn — đừng ghi "gate kiểm tra `Lessons áp dụng`" vào báo cáo.

Nạp skill `project-lessons` **trước** khi lập plan.

## 8. Báo cáo phải phân biệt 3 trạng thái

- **PASS** — đã chạy, đo được, exit code ghi kèm.
- **CHƯA CHẠY** — chưa chạy (thiếu credential, thiếu mạng, bị Owner dừng). Ghi rõ lý do. **Không suy diễn thành PASS.**
- **KNOWN-RED** — đỏ có sẵn ở HEAD, gate cho qua nhưng in ra để không bị che.

Đây là L-E02/L-E07. Báo cáo nào ghi "PASS" cho thứ chưa chạy là finding, không
phải khoảng trắng.