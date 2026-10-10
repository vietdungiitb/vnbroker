---
name: project-lessons
description: >-
  Nạp kinh nghiệm theo ngữ cảnh cho repo vnbroker. Chỉ đọc các file lesson liên quan
  (trích theo tag từ mô tả task + đường dẫn file), rồi trả về checklist "LESSONS
  APPLICABLE" ngắn gọn PHẢI được phản ánh trong plan dưới dạng
  "Lessons áp dụng: [...]". Dùng TRƯỚC khi lập kế hoạch, khai claim, hoặc viết dòng code
  đầu tiên — đặc biệt mọi việc chạm broker lane (tiền thật, write endpoint, token,
  lệnh), đối chiếu spec TCBS, đo lường/bằng chứng, worktree/junction, hay claim
  nhiều agent. Ngăn lặp lại những sai lầm quy trình đã ghi ở docs/LESSONS/.
---

# project-lessons (vnbroker)

## Mục đích

Biến "kinh nghiệm nhỏ lỗi" thành **"kinh nghiệm bắt buộc kiểm tra"** tại thời điểm lập
kế hoạch. Đọc **chỉ** phần lesson liên quan (theo tag), trả checklist ngắn.

**KHÔNG** đọc toàn bộ `docs/LESSONS/` — mục tiêu là tránh context bloat.

## Khi nào dùng

Bắt buộc trước khi:
- Tạo todo list / kế hoạch chi tiết
- Khai claim trong `docs/CLAIMS.md`
- Bắt đầu sửa dòng code đầu tiên
- **Thêm/sửa bất kỳ method nào trong `vnbroker/broker/`** (lane tiền thật)

Đây là **Planning Gate**.

## Input

| Tham số | Bắt buộc | Mô tả |
|:--|:-:|:--|
| `taskDescription` | Có | Mô tả task/slice đang làm |
| `filePaths` | Không | Danh sách file dự kiến sửa (giúp suy tag) |
| `actions` | Không | Hành động dự kiến: `edit`, `claim`, `gate`, `test`, `measure`, `probe` |

## Step 1 — Trích tag

Suy tag (case-insensitive) từ `taskDescription` + `filePaths` + `actions`:

| Từ khóa / Path | File cần đọc |
|:--|:--|
| `broker/`, `money`, `tiền`, `write`, `order`, `lệnh`, `token`, `jwt`, `auth`, `session`, `otp`, `rc`, `dry_run`, `write_gate`, `margin`, `nộp`, `rút`, `chuyển`, `fill`, `cancel`, `tcbs` | `docs/LESSONS/broker-risk.md` |
| `claim`, `slice`, `worktree`, `junction`, `cleanup`, `rmdir`, `agent`, `audit`, `AC`, `budget`, `fat-file`, `800L`, `design`, `feasible`, `__init__`, `export`, `facade`, `handoff` | `docs/LESSONS/process.md` |
| `count`, `measure`, `verify`, `verify:`, `PASS`, `CHƯA CHẠY`, `CHUA CHAY`, `NOT MEASURED`, `proof`, `fail-before`, `flake`, `pytest`, `skip`, `baseline`, `spec`, `openapi`, `sha`, `sha256`, `drift`, `citation`, `criteria`, `legacy`, `xoá`, `remove`, `test`, `regression`, `encoding` | `docs/LESSONS/evidence.md` |

### Quy tắc an toàn (fallback) — ưu tiên bắt hơn suy luận

- Có **bất kỳ** `claim` `slice` `worktree` `budget` `agent` `audit` `AC`
  → **luôn** nạp `process.md`.
- Có **bất kỳ** `PASS` `CHUA CHAY` `CHƯA CHẠY` `measure` `verify` `proof` `spec` `baseline`
  → **luôn** nạp `evidence.md`.
- Chạm `vnbroker/broker/**` hoặc từ khóa tiền/lệnh/token
  → **luôn** nạp `broker-risk.md`. Lane này là **tiền thật**, mặc định là mọi thứ.

## Step 2 — Đọc file lesson

Đọc **trên về** 1–2 file tương ứng (mỗi file ≤ 120 dòng theo C1).
KHÔNG đọc `docs/LESSONS/` toàn bộ.
Nếu file không tồn tại → ghi `LESSONS: file KHÔNG TỒN TẠI` (không đoán nội dung).

## Step 3 — Trích checklist

Từ mỗi lesson khớp tag, lấy đúng `QUY TẮC` + các mục `- [ ]` trong `CHECKLIST`.
Bỏ qua lesson không khớp tag.

## Step 4 — Trả về

Format output **bắt buộc**:

```text
LESSONS APPLICABLE (<n>):
- [L-R01 | tiền thật] - QUY TẮC: HTTP 200 có thể là thất bại nghiệp vụ, caller phải tự kiểm rc

MANDATORY CHECKLIST:
- [ ] <item 1>
- [ ] <item 2>

FILES READ: <danh sách đầy đủ file đã đọc>
```

**Giới hạn: tối đa ~20 dòng.** Vượt thì giữ các mục rủi ro cao nhất — ưu tiên mục `KHÔNG`/`PHẢI`.

**Quy tắc C3:** task đã miễn nhiệm được đọc nhiều nhóm, nhưng `FILES READ` phải liệt kê
**đủ tên file** — để thấy được nhóm nào đã bị bỏ sót.

**Không khớp lesson nào:**
```text
LESSONS APPLICABLE: NONE
Lý do: <ngắn gọn>
FILES READ: (none)
```

## Step 5 — Áp dụng vào plan (bắt buộc)

Plan PHẢI chứa **một trong hai dòng**:

- `Lessons áp dụng: [L-R01, L-P03]`
- `Lessons áp dụng: NONE - <lý do ngắn>`

Và phải **tick từng mục trong `MANDATORY CHECKLIST`** trước khi coi slice là xong.

## Anti-pattern (KHÔNG làm)

| Sai lầm | Vì sao sai |
|:--|:--|
| Đọc toàn bộ `docs/LESSONS/` | Context bloat, agent skim một tập trung |
| Gọi skill nhưng không ghi `Lessons áp dụng` vào plan | Không ai kiểm chứng được → quy tắc không thi hành được |
| Tự thêm lesson mới vào `docs/LESSONS/` | Cần coordinator duyệt (INDEX §1.3) |
| Suy nội dung lesson khi chưa đọc file | Vi phạm nguyên tắc — xem L-E06 |
| Bỏ qua fallback vì "task không liên quan" | Đây là nhóm nhầm lẫn tần suất cao nhất |
| **Gộp mọi lesson vào một file cho "gọn"** | Một file > 120 dòng → đọc lướt/cắt. Vi phạm C1 |
| **Bỏ nhóm `broker-risk` vì task "chỉ sửa docs"** | Sửa doc của write endpoint mà không nạp lesson tiền thật là lập luận sai |
| **Tăng ngưỡng C1/C2 khi bị vượt** | Đổi ngưỡng để giữ lỗi — xem L-E01 |

## Cross-reference

- Quy tắc gốc + 3 quy tắc cứng: `docs/LESSONS/INDEX.md`
- Quy trình + ngân sách dòng: `CLAUDE.md`
- Claim registry: `docs/CLAIMS.md`
- Bằng chứng gốc: `docs/REPORT_TCBS_ROUND2.md` · `CHANGELOG.md`
- Machine gate cho 3 quy tắc cứng:
  `.venv\Scripts\python.exe scripts\check_lessons.py` (+ `--self-test`)