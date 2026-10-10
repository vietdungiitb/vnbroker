# LESSONS — Sổ tay kinh nghiệm vận hành (vnbroker)

> Sổ tay này chỉ chứa **sai lầm đã thật sự xảy ra trong repo này** và đã tốn thời gian
> đo đạc. Mục đích: **phòng ngừa lặp lại**, không phải lưu lịch sử.
>
> Phân biệt bắt buộc:
> - **`CHANGELOG.md`** = *đã xảy ra gì* (append-only)
> - **`docs/LESSONS/`** (file này) = *phải tránh gì* (playbook + checklist dòng dưới)
> - **`CLAUDE.md`** = *quy ước sản phẩm* + ngân sách dòng
> - **`docs/CLAIMS.md`** = *claim registry* (append-at-end)
> - **`docs/REPORT_TCBS_ROUND2.md`** = *báo cáo vòng vừa rồi* + bàn giao
>
> Skill [`project-lessons`](../../.opencode/skills/project-lessons/SKILL.md) chỉ đọc
> **1–2 nhóm** theo tag, không đọc cả sổ tay.
>
> **Nguồn mẫu:** `C:\Mujoco Projects\vninvestcharts-widget\docs\LESSONS\` (gate
> `check-lessons.cjs`) và `C:\Mujoco Projects\vninvest\docs\LESSONS\`. **Adapt, không copy:**
> lesson của repo đó nói về engine/React/npm; ở đây phần lớn là broker lane, tiền thật và
> đối chiếu spec TCBS. Cổng machine ở đây viết bằng **Python** cho khớp stack repo
> (`scripts/check_lessons.py`), không phải Node.

---

## §1.1 Bảng tag → file

| Tag chính | File | Phạm vi |
|:--|:--|:--|
| `count` `measure` `plan` `doc-drift` `spec` `pin` `evidence` `reproducible` `drift` `sha256` `crlf` `gitattributes` `autocrlf` `false-alarm` `flake` `network` `pytest` `collect` `skip` `baseline` `compare` `criteria` `legacy` `remove` `test` `fail-before` `proof` `proxy` `vacuuous` `regression` | [`evidence.md`](./evidence.md) | Đo lường, bằng chứng, trích dẫn, self-verify |
| `worktree` `env` `venv` `claim` `slice` `ownership` `init` `export` `facade` `plan` `contradiction` `budget` `fat-file` `design` `agent` `trust` `audit` `AC` `review` `junction` `rmdir` `cleanup` `windows` `destructive` `feasible` `unsatisfiable` | [`process.md`](./process.md) | Chia việc multi-agent, worktree, claim, kết quả trung thực |
| `money` `write` `gate` `guards` `signature` `safety` `dry-run` `rc` `business-code` `idempotency` `tcbs` `json` `get` `null` `optional` `response` `parse` `probe` `401` `routing` `unverifiable` `legacy` `auth` `token` `jwt` `exp` `ttl` `session` `status` `4xx` `error-mapping` `_write_http` `pin` `field name` `heuristic` `dangerous` | [`broker-risk.md`](./broker-risk.md) | **An toàn tiền thật** — đọc bắt buộc trước mọi sửa `vnbroker/broker/` |
| `gate` `gates` `coverage` `AST` `AnnAssign` `keywords` `blind spot` `self-test` `exit code` `enforce` `baseline` `ratchet` `waiver` `false green` `scope` | [`gate-integrity.md`](./gate-integrity.md) | Cổng tự báo xanh nhưng không kiểm đủ; baseline xanh giả; gợi ý gây sai |

### Quy tắc an toàn (fallback) — ưu tiên bắt hơn suy luận

Task có **bất kỳ** từ khóa nào: `claim` `slice` `worktree` `budget` `design` `agent`
`audit` `AC` `feasible`
→ **luôn** nạp [`process.md`](./process.md), bất kể suy ra được tag gì.

Task có `PASS` `CHUA CHẠY` `measure` `verify` `proof` `fail-before` `sha256` `spec`
`baseline` `flake` `pytest` `citation`
→ **luôn** nạp [`evidence.md`](./evidence.md).

Task chạm `broker/` `money` `write` `token` `auth` `order` `tcbs` `rc` `dry_run`
→ **luôn** nạp [`broker-risk.md`](./broker-risk.md). Đây là lane tiền thật.

Sửa hoặc viết **cổng/script kiểm tra** (`scripts/`, hook, `check_*`)
→ **luôn** nạp [`gate-integrity.md`](./gate-integrity.md).

---

## §1.2 Ba quy tắc cứng về cấu trúc

Cấu trúc file ở đây **dành cho giới hạn đọc của máy**, không phải thẩm mỹ tài liệu.
Vì vậy *"gom về một file cho gọn"* là **sai** — biến một lựa chọn đọc lướt thành quy tắc.

| # | Quy tắc | Vì sao |
|:--|:--|:--|
| **C1** | Một file lesson **≤ 120 dòng** (không tính dòng trống) → **tách tiếp** | Skill luôn đọc **trên về** 1 file. Dưới ngưỡng này không bảo đảm rằng cả luật đọc được trong 1 lần. |
| **C2** | Tổng số lesson **≤ 40**. Vượt → **gộp lesson trùng lặp**, KHÔNG thêm file | Vượt ngưỡng thường là hiện tượng viết 2 lesson cho cùng một lỗi sai, hoặc ghi quy tắc chưa từng gây lỗi. |
| **C3** | Task đã miễn nhiệm được đọc **nhiều nhóm**, nhưng phải báo **đủ tên file** trong `FILES READ` | Chống "chỉ đọc 1 file cho chắc rồi im thôm nhóm còn lại". |

Đã tự động hoá thành gate — không đếm tay:

```powershell
.venv\Scripts\python.exe scripts\check_lessons.py            # C1 + C2 + DRIFT
.venv\Scripts\python.exe scripts\check_lessons.py --self-test # 9 case âm thực
```

> ⚠ **Không đếm C1 bằng `Get-Content | Measure-Object -Line`** — lệnh đó **không** đếm
> dòng trống và bỏ BOM, nên lệch với gate 10–29 dòng mỗi file. Gate đọc UTF-8 và đếm
> dòng **không trống**; hai phương pháp cho hai con số khác nhau.

---

## §1.3 Quy tắc nhận lesson mới

Chỉ thêm entry mới khi **ĐỦ THỎA** cả 4 điều kiện:

- **Đã xảy ra thật** — có bằng chứng: entry `CHANGELOG.md` / `docs/REPORT_*.md` /
  commit cụ thể, hoặc output lệnh đã dán.
- **Gây hậu quả rõ** — tốn vòng audit, làm N test đỏ, sai số liệu nghiệm thu, hoặc
  công việc đã commit.
- **Phòng ngừa được** — có `CHECKLIST` cụ thể trả lời Có/Không.
- **Atomic** — 1 bài học = 1 lỗi sai.

**KHÔNG** đưa vào nếu quy tắc đã có ở `CLAUDE.md` hoặc `docs/AGENT_PROTOCOL.md`
nhưng **chưa từng gây lỗi** ⇒ thuộc phạm vi quy tắc, không phải bài học. Nếu **đã từng
gây lỗi** thì viết thành checklist ngắn ở đây.

**Cần coordinator duyệt** trước khi thêm — `docs/LESSONS/` là tài liệu shared, mọi agent
đều đọc; hai agent cùng viết một lesson loại đã xảy ra (`CLAIMS.md` từng có 3 định nghĩa
"G1–G8" ở 3 nơi).

---

## §1.4 Format chuẩn của một lesson

```markdown
## L-XX: [Tiêu đề phản ánh đúng lỗi đã gặp]

- **Sai lầm:** Nguyên nhân.
- **Hậu quả thật:** Hậu quả **đo được**. KHÔNG viết "có thể gây".
- **Tags:** `tag1`, `tag2`
- **QUY TẮC:** "KHÔNG ... / PHẢI ..."
- **CHECKLIST:**
  - [ ] Câu hỏi kiểm tra cụ thể, trả lời Có/Không
- **Proof:** `path:line @ <short-sha>` | entry `docs/REPORT_*.md` | commit hash | output lệnh
```

> Giữ format ngắn — đây là điều kiện C1 (≤ 120 dòng/file) khả thi. Một lesson dài không
> phải lesson tốt; nó là một tài liệu nền nằm ở `docs/`.
>
> ?? **Proof phải kèm `@ <short-sha>`.** Số dòng trôi theo thời gian; không có sha thì
> citation hỏng im lặng. Proof cũng nên kèm **lệnh tái lập** nếu là con số.

---

## §1.5 Trạng thái

| Nhóm | Lesson | Nguồn |
|:--|:--|:--|
| [`evidence.md`](./evidence.md) | L-E01..L-E07 (7) | Đợt TCBS 1–2: `docs/SUMMARY_TCBS_REBUILD.md:98-109,158-161` · `docs/PLAN_TCBS_ROUND2.md` §0,§1 · commit `3e252ac`, `bc9d786` |
| [`process.md`](./process.md) | L-P01..L-P06 (6) | `docs/PLAN_AUDIT_TCBS_ROUND2.md` C-5/F-3/F-5 · `docs/PLAN_TCBS_ROUND2.md` §5b · commit `c8c4618`, `f23786f` |
| [`broker-risk.md`](./broker-risk.md) | L-R01..L-R07 (7) | `docs/REPORT_TCBS_ROUND2.md` §6 R1/R2 · `docs/AUDIT_ROUND3.md` F-5 (gợi ý `pinCode->price`) · commit `d7d75ca`, `bc9d786`, `ee0fbc5` |
| [`gate-integrity.md`](./gate-integrity.md) | L-G01..L-G04 (4) | Audit round 3 (bản 3 lỗi phủ + self-test không ép + baseline quá thô) · commit `93a89e8`, `ee0fbc5` |

**Tổng: 24 lesson / 4 file** — dưới C2 (40), mọi file dưới C1 (120 dòng).
Citation kiểm chứng tại `sha = ee0fbc5`. Gate `check_lessons.py` tự kiểm C1/C2 + số liệu
bảng này — sửa bảng mà quên sửa file thì gate báo `DRIFT`.

> **Round 3 là vòng sinh ra nhiều bài học nhất về chính công cụ kiểm tra**: 4/4 lesson
> trong `gate-integrity.md` đều là lỗi của cổng do tôi viết trong cùng phiên. Đó là
> lý do nhóm này tồn tại: **cổng mới luôn cần audit độc lập, không tự chứng minh được**.

> Nguồn mẫu từ `vninvestcharts-widget` (`check-lessons.cjs`) và `vninvest`
> (`docs/LESSONS/`). Ở vninvest **chưa có** machine gate cho thư mục này; ở đây có —
> vì đó là điểm khác biệt có chủ đích, không phải sao chép hình thức.