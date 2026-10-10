# Process — Quy trình multi-agent, worktree, claim, kết quả trung thực

> Nhóm bài học về **cách chia việc**. Ở repo này một sai lầm quy trình không tốn một
> commit, mà tốn **một cả lát công việc**.

## L-P01: Worktree không có `.env` và `.venv` — baseline đo ở đâu là quan trọng

- **Sai lầm:** Có xu hướng ép số baseline của main tree vào báo cáo của worktree.
- **Hậu quả thật:** Worktree **không có** `.env` (bị gitignore) và `.venv`. Test bỏ qua vì
  thiếu biến môi trường ⇒ số test **khác hẳn**. Ép khớp số là bịa bằng chứng.
- **Proof:** `docs/SUMMARY_TCBS_REBUILD.md:158-161` §10.2 — 3 agent đợt 1 đều **làm đúng**
  khi tự đo baseline của worktree; nếu làm ngược thì số sai.
- **Tags:** `worktree`, `env`, `venv`, `baseline`, `honest`
- **QUY TẮC:** Ghi rõ **số đo ở đâu** (main tree hay worktree, commit nào). Worktree đo
  được gì thì báo đó, không sửa cho khớp main tree.
- **CHECKLIST:**
  - [ ] Số trong báo cáo ghi kèm **nơi đo** (main tree / worktree) + commit?
  - [ ] Có biến môi trường nào chỉ có ở main tree không?
  - [ ] Nếu thiếu môi trường ⇒ gate đó ghi **CHƯA CHẠY**, không kết luận từ suy luận?

## L-P02: Gỡ junction `.venv` TRƯỚC khi xoá worktree

- **Sai lầm:** Tạo junction `.venv` cho worktree để tiết kiệc ~500 MB, rồi có thể gọi
  xoá đệ quy trên cây worktree.
- **Hậu quả thật:** `rmdir /s` xuyên qua junction sẽ xoá **thư mục đích** — tức `.venv`
  chính của main tree. Đã xảy ra thật ở repo khác trong hệ sinh thái (2026-09-28,
  `node_modules` chính còn 0 entry).
- **Proof:** đo `Get-Item .venv -Force` ⇒ `LinkType=Junction`,
  `Attributes=Directory, ReparsePoint` trên cả 3 worktree của đợt 2. Quy trình đúng:
  `cmd /c rmdir <worktree>\.venv` (không `/s`) → `git worktree remove` → xác nhận main
  `.venv` còn nguyên 255320 B.
- **Tags:** `worktree`, `junction`, `rmdir`, `cleanup`, `windows`, `destructive`
- **QUY TẮC:** Junction/symlink **không bao giờ** nằm trong cây bị xoá đệ quy. Gỡ riêng
  junction trước (không `/s`), rồi mới xoá cây.
- **CHECKLIST:**
  - [ ] Đã liệt kê junction/symlink trong worktree **trước khi** xoá?
  - [ ] Gỡ junction bằng lệnh **không** `/s` chưa?
  - [ ] Xác nhận `.venv`/`node_modules` **chính** còn nguyên sau khi xoá?
  - [ ] Script dọn dẹp có **dry-run mặc định** + cờ `--execute` không?

## L-P03: Cấm chạm file X nhưng bắt ghi vào X — mâu thuẫn thiết kế, phải chốt TRƯỚC

- **Sai lầm:** Plan cấm chạm `derivatives.py` (852L, đã vượt ngân sách 800L) nhưng lại
  giao endpoint `condition/cancel` thuộc **đúng họ** với 3 endpoint đang nằm trong đó
  (`condition/place`, `v2/condition/change`, `condition/detail`). Audit độc lập gọi đây là
  **mâu thuẫn nội tại của plan**.
- **Hậu quả thật:** Ba lựa chọn, cái nào cũng có giá: (a) nhét vào `derivatives.py` → 852→880L,
  vượt thêm; (b) tách HTTP helper dùng chung → phải refactor file 852L giữa đợt đang làm
  feature; (c) file mới tự mang `_post` → nhân bản code. Chọn sai là lãng phí cả lát.
- **Proof:** `docs/PLAN_AUDIT_TCBS_ROUND2.md` F-3 (blocker); quyết định chốt ở
  `docs/PLAN_TCBS_ROUND2.md` §5b — phương án (c), nợ N8 ghi rõ.
- **Tags:** `plan`, `contradiction`, `budget`, `fat-file`, `design`, `slice`
- **QUY TẮC:** Trước khi giao agent: **đọc code vị trí định đặt** và hỏi "file này có import
  từ file bị cấm không, và có lớn hơn ngân sách không?". Nếu câu trả lời là có ⇒ **chốt
  phương án trong plan**, không đẩy xuống cho agent tự quyết.
- **CHECKLIST:**
  - [ ] Module mới có cần import từ file bị cấm chạm không?
  - [ ] File định đặt có đang **sát/vượt** ngân sách dòng không?
  - [ ] Nếu phải nhân bản code, đã ghi nợ tái trả chưa?
  - [ ] Đã chốt phương án **trong plan** trước khi giao agent chưa?

## L-P04: File không có chủ ⇒ hoặc tranh chấp, hoặc export hỏng

- **Sai lầm:** Plan giữ `client.py` cho coordinator nhưng quên `__init__.py`. Cả 3 lát đều
  tạo symbol mới cần vào `__all__`.
- **Hậu quả thật:** Hoặc 3 agent tranh nhau sửa một file 40 dòng, hoặc service mới không
  được export ⇒ `from vnbroker.broker.tcbs import TCBSConditionOrderService` fail ở
  chỗ người dùng, không phải chỗ viết.
- **Proof:** `docs/PLAN_AUDIT_TCBS_ROUND2.md` C-5 / F-5 (major); sửa ở
  `docs/PLAN_TCBS_ROUND2.md` §5b.
- **Tags:** `plan`, `ownership`, `init`, `export`, `facade`, `slice`
- **QUY TẮC:** Lập bảng "ai giữ file nào" cho **mọi** file có thể bị chạm, kể cả file
  nhỏ vô hình (`__init__.py`, barrel export, index). File không có chủ = lỗ hổng.
- **CHECKLIST:**
  - [ ] Bảng phân công có **mọi** file liên quan, không chỉ file "chính" không?
  - [ ] Có file barrel/export/`__init__.py` nào cần sửa không? Ai giữ?
  - [ ] Facade (`client.py`) có đủ wrapper cho method mới không, và ai thêm?
  - [ ] Đã kiểm import được từ package root (`python -c "from ... import ..."`)?

## L-P05: Tin lời agent là tin người khác nói đúng — hãy đo lại

- **Sai lầm:** 3 agent đều báo "AC đạt hết" (24/24). Tôi chạy gate thì xanh. Nhưng audit
  độc lập đọc code tìm ra **2 lỗi major nằm ngoài AC** mà **không agent nào nêu**.
- **Hậu quả thật:** `money.py._post` chỉ map 401/403/5xx ⇒ **400/404/422/429 rơi qua**,
  `resp.json()` trả về y như thành công — với write động tiền. Không chỗ nào kiểm mã
  nghiệp vụ `rc`. Cả 4 cảnh báo "ngoài phạm vi" mà agent nêu đều đúng và đều bị đánh giá
  thấp; 2 lỗi nặng nhất thì không ai nêu vì **không nằm trong AC**.
- **Proof:** `bc9d786`; bằng chứng đo trong §6 `docs/REPORT_TCBS_ROUND2.md` — 4/4 test
  `DID NOT RAISE` trên `money.py` bản cũ `90ead64`.
- **Tags:** `agent`, `trust`, `audit`, `AC`, `review`, `proxy`
- **QUY TẮC:** Agent tự báo AC đạt là **bằng chứng yếu nhất**. Coordinator phải (1) chạy
  lại gate, (2) đọc code vùng rủi ro, (3) có auditor độc lập read-only. AC chỉ bảo phủ —
  **lỗi quan trọng nhất thường nằm ngoài AC**.
- **CHECKLIST:**
  - [ ] Đã **tự chạy lại** gate, không dùng số agent báo?
  - [ ] Đã đọc code vùng rủi ro (write path, auth, money) bằng mắt?
  - [ ] Có auditor **read-only** riêng không?
  - [ ] Đã hỏi: *"lỗi nào **không ai** trong 3 agent nhắc tới?"*

## L-P06: AC phải thi hành được — đừy đòi thứ mà nguồn sự thật không có

- **Sai lầm:** Kế hoạch cũ (được viết từ tài liệu web) yêu cầu *"TokenManager tự refresh
  trước 5 phút"*. Spec TCBS **không có endpoint refresh token** nào — chuỗi `refresh`
  trong toàn spec = **0 lần**.
- **Hậu quả thật:** AC đó **không thi hành được**. Ai viết code theo đều phải bịa một
  endpoint, hoặc âm thầm không làm gì rồi báo xong. Đây là dạng "tiêu chí chấp nhận không
  tương thích" — tốn ít nhất một vòng audit mới phát hiện.
- **Proof:** `docs/PLAN_TCBS_ROUND2.md` §1 P1 (đếm `refresh` = 0);
  `docs/PLAN_AUDIT_TCBS_ROUND2.md` §4 (AC proxy) — audit đánh dấu T3/T9/T10 là proxy.
- **Tags:** `AC`, `plan`, `feasible`, `unsatisfiable`, `spec`
- **QUY TẮC:** Trước khi viết AC, hỏi: *"cơ chế này có **tồn tại** trong nguồn sự thật
  không?"*. AC mà không làm được thì **đổi AC**, đừng đổi để code khớp.
- **CHECKLIST:**
  - [ ] Mỗi AC có cơ chế kỹ thuật **tồn tại** trong spec/API thật không?
  - [ ] AC có **chỉ số quan sát được** không, hay chỉ là proxy ("trả về 200")?
  - [ ] Nếu AC không thi hành được ⇒ đã **đổi AC** + ghi lý do, chưa giao agent?
  - [ ] Baseline của từng gate đã **đo trước** khi đòi kết quả? (đừng đòi PASS từ gate đang đỏ)