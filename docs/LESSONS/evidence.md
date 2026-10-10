# Evidence — Bằng chứng, đo lường, trích dẫn

> Nhóm bài học về **cách ta biết mình đúng**. Ở repo này sai lầm đắt nhất không phải
> code hỏng, mà là **kết luận sai vẫn được báo PASS**.

## L-E01: Không đếm bằng mắt — số trong tài liệu cũ đã lỗi thời

- **Sai lầm:** Kế hoạch cũ ghi *"13/48 endpoint chưa dùng"*. Đếm lại bằng script AST trên
  spec cho ra **9**.
- **Hậu quả thật:** 4 "endpoint còn nợ" trong danh sách đã xong ở đợt trước
  (`bars`, `bars-long-term` nối ở GĐ1; `gaia/…/token` và `campaign-management/…/addons/detail`
  đã nối từ lâu). Nếu tin tài liệu thì 4 lát nữa sẽ viết lại code đã có, hoặc báo Owner
  "còn nợ 13" khi thực tế còn 9.
- **Proof:** đo được `48 path · 39 đã nối · 9 chưa` @ `ddc1a8a`; danh sách 13 sai lệch ở
  `docs/PROPOSAL_TCBS_REBUILD_20261009.md` §7 (viết 2026-10-09, sai ngay từ đầu).
  Lệnh tái lập: `.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py`
- **Tags:** `count`, `measure`, `plan`, `doc-drift`, `spec`
- **QUY TẮC:** Mọi con số trong plan phải **kèm lệnh tái lập được**. Không có lệnh ⇒
  ghi `ƯỚC LƯỢNG` hoặc xoá. Số trong tài liệu cũ **mặc định là đã hỏng**.
- **CHECKLIST:**
  - [ ] Mỗi con số trong plan/report có **1 dòng lệnh** tạo ra nó, và đã chạy ở **đúng commit**?
  - [ ] Số đếm bằng AST/script ⇒ đã **chạy script**, không đếm tay, không regex thô?
  - [ ] Số lấy từ tài liệu cũ đã kiểm lại bằng **nguồn sự thật** (spec/code) chưa?

## L-E02: Spec / pin đánh giá phải nằm trong repo

- **Sai lầm:** Đợt 1 đối chiếu mọi thứ với `~/Downloads/openapi-v1.0.0.json` — file nằm
  ngoài repo, **không ai tái lập lại được** sau khi máy đổi.
- **Hậu quả thật:** Cả 3 lát của đợt 2 đều dựa vào tiền đề lấy từ file không tồn tại trong
  repo. Khi tôi tìm lại, tôi tìm thấy `docs/references/tcbs_iflash_openapi.json` — bản
  **spec cũ, trước 1.0.0, untracked** — và nó **có đủ 18 path `/erebos/*`** mà đợt 1 đã gỡ.
  Đối chiếu nhầm file này sẽ kết luận ngược "gỡ nhầm 18 endpoint".
- **Proof:** `docs/references/openapi-v1.0.0.json` (sha256 `7f97d27b…42bd4a`) được commit
  ở `c8c4618`; bản cũ xoá cùng commit. Gate `verify_tcbs_coverage.py` **tự kiểm sha256**.
- **Tags:** `spec`, `pin`, `evidence`, `reproducible`, `drift`
- **QUY TẮC:** Mọi spec/pin đánh giá phải **commit vào repo kèm sha256**, và gate tự kiểm
  sha đó. Không chạy được vì "file trên máy tôi" ⇒ **KHÔNG CHẠY**, không phải PASS.
- **CHECKLIST:**
  - [ ] File định nghĩa hợp đồng (spec, schema, baseline) đã **commit trong repo** + có sha256?
  - [ ] Tồn tại **nhiều bản** của file này trong repo không? (`docs/references/` hay bị lẫn — đã có 1 bản spec cũ ở đó)
  - [ ] Thư mục chứa file đó đang `.gitignore` ⇒ mở **đúng 1 file** bằng negation, **không** mở cả thư mục (có thể chứa credential thật)?

## L-E03: Gate băm sha256 bị CRLF phá trước khi ai kịp dùng

- **Sai lầm:** Commit spec với sha256 `7f97d27b…`. Tạo worktree → gate báo
  `spec sha256 lech`, sha thực tế `1cf72672…`. Repo bật `core.autocrlf=true`;
  `.gitattributes -text` **không** thắng, blob trong git đúng từng byte nhưng bản làm
  việc vẫn CRLF (4105 ký tự `\r\n`).
- **Hậu quả thật:** Nếu không kiểm, mọi agent chạy trong worktree đều gặp gate đỏ giả và
  hoặc báo FAIL, hoặc — tệ hơn — tắt gate. Đây là lần thứ 2 trong đợt (lần 1 là tôi tưởng
  `.gitattributes` đã sửa xong và bỏ qua).
- **Proof:** đo trên `C:\Mujoco Projects\tcbs-t-token` — blob git sha `7f97d27b…`,
  file làm việc sha `1cf72672…`, sau `replace(b"\r\n", b"\n")` khớp `7f97d27b…`.
  Sửa ở `3e252ac`.
- **Tags:** `gate`, `sha256`, `crlf`, `gitattributes`, `autocrlf`, `false-alarm`
- **QUY TẮC:** Gate **tự kiểm** input trước khi tin nó, và **phải chạy trong worktree**
  chứ không chỉ ở main tree. Gate đỏ ở worktree nhưng xanh ở main ⇒ **nghi ngờ EOL
  trước khi nghi ngờ nội dung**.
- **CHECKLIST:**
  - [ ] Gate chạy ở **worktree** ít nhất 1 lần, không chỉ main tree?
  - [ ] Hash có chuẩn hoá line-ending trước khi băm?
  - [ ] Đã kiểm `git check-attr text -- <file>` xem `.gitattributes` **thực sự** có hiệu lực? (`core.autocrlf` ở repo này là `true`)

## L-E04: Một lần gate đỏ không phải kết luận

- **Sai lầm:** Chạy `pytest tests/ -q` một lần ra `1 failed, 1695 passed`. Chạy lại ra
  `1696 passed, 26 skipped`. Test đỏ là `tests/integration/test_news_integration.py`, gọi
  mạng thật `kbbuddywts.kbsec.com.vn`, read timeout 30 s.
- **Hậu quả thật:** Đây là **lần thứ 3** trong hai đợt liên tiếp mà một lần chạy đơn lẻ
  dẫn tới kết luận sai — suýt báo FAIL hoặc báo PASS cho một thứ chưa ổn định.
- **Proof:** `docs/SUMMARY_TCBS_REBUILD.md:56-69` (đợt 1, §4) và đợt 2 §0 baseline
  ghi lại **cả hai** lần chạy. Đợt 1 suýt báo PASS "không trung thực nếu chỉ nhìn 1 lần".
- **Tags:** `flake`, `network`, `pytest`, `test`, `gate`, `retest`
- **QUY TẮC:** Kết luận đỏ **phải chạy lại lần hai** trước khi báo. Báo cáo phải ghi **cả
  hai lần**. Test chạm mạng thật = **không** phải gate phát hành.
- **CHECKLIST:**
  - [ ] Khi gate đỏ, đã **chạy lại lần 2** chưa?
  - [ ] Nếu lần 2 khác lần 1 ⇒ báo cáo ghi **cả hai**, không chỉ lần đẹp?
  - [ ] Test có chạm mạng thật không? (`kbbuddywts`, `openapi.tcbs.com.vn`, DNS ngoài)
  - [ ] Có mark là flaky + lý do trong báo cáo không?

## L-E05: Tiêu chí lọc phải là "vắng ở path cụ thể", không phải "vắng ở tiền tố"

- **Sai lầm:** Tôi phát biểu *"19 path legacy là những path có tiền tố `erebos`/`aion`"*.
  Tiêu chí sai: spec chính thức **có** `/erebos/v2/digital/margin-info` và
  `/erebos/v2/digital/trans-hist-cashStatements` (có trong cả spec lẫn Postman).
- **Hậu quả thật:** Nếu tin tiêu chí cũ thì đã **xoá nhầm 2 path đang hoạt động**.
  Kết quả gỡ 18 path vẫn đúng, nhưng chỉ **vì** đã xác minh lại từng cái theo path.
- **Proof:** `docs/SUMMARY_TCBS_REBUILD.md:98-109` §5 (đính chính của chính audit tôi).
- **Tags:** `criteria`, `legacy`, `remove`, `false-positive`, `spec`
- **QUY TẮC:** Tiêu chí lọc phải kiểm **giá trị cụ thể**, không kiểm **mẫu hình**. Muốn
  xoá gì đó ⇒ lập bảng **từng mục** với bằng chứng "có/không trong nguồn", rồi đối chiếu
  **từng dòng**.
- **CHECKLIST:**
  - [ ] Mỗi mục có **bằng chứng từng dòng**, không chỉ đếm tổng?
  - [ ] Có mục nào "đúng theo mẫu hình nhưng vắng ở path cụ thể" không? (⇒ tiêu chí hỏng)
  - [ ] Sau khi xoá, đã đếm lại cái **còn lại** và đối chiếu độc lập chưa?

## L-E06: Bằng chứng fail-trước phải chạm đúng tầng lỗi

- **Sai lầm:** Viết test đầu tiên cho lỗi "write 4xx bị nuốt" là assert cấu trúc
  (`'_post' phải gọi helper`). Test đó **ĐỎ** trên code cũ — nhưng vì lý do sai: nó kiểm
  *hình thức*, không kiểm *lỗi*. Người đọc dễ tưởng đã có bằng chứng.
- **Hậu quả thật:** Test phải gọi **hàm thật** với **input gây lỗi thật** mới chứng minh lỗi
  tồn tại. Khi thay bằng `deposit_margin(dry_run=False)` với HTTP 400, cả 4 mã
  400/404/422/429 ra `DID NOT RAISE` trên code cũ — bằng chứng định lượng thật.
- **Proof:** commit `bc9d786`; lệnh tái lập fail-trước:
  `git show 90ead64:vnbroker/broker/tcbs/money.py > <file>` rồi chạy
  `pytest tests/unit/broker/tcbs/test_tcbs_write_http.py` ⇒ `5 failed, 27 passed`.
- **Tags:** `test`, `fail-before`, `proof`, `proxy`, `vacuuous`, `regression`
- **QUY TẮC:** Test chứng minh lỗi phải **gọi code thật** với input gây lỗi thật, và
  **ĐỎ trước / XANH sau**. Assert hình thức (tên hàm, có import, có chuỗi) là **bằng
  chứng vô giá trị** — nó xanh cả khi lỗi vẫn còn.
- **CHECKLIST:**
  - [ ] Test mới **ĐỎ** trên bản trước thay đổi? (dán lệnh + output, không mô tả)
  - [ ] Test gọi **hàm thật** chứ không chỉ đọc source/import?
  - [ ] Input trong test là input **thật sự gây lỗi**?
  - [ ] Test có **xanh cả trước và sau** không? (⇒ bằng chứng = 0)

## L-E07: Tổng số test biến động theo mạng — đừng so 2 con số của 2 lần chạy

- **Sai lầm:** `1696 passed + 26 skipped = 1722` nhưng `pytest --collect-only` ra
  `1719 collected`. Tưởng gate không nhất quán.
- **Hậu quả thật:** Module gọi `pytest.skip(allow_module_level=True)` khi kiểm tra môi
  trường ⇒ số item **thu thập** phụ thuộc trạng thái mạng tại thời điểm collect. Không
  phải gate sai.
- **Proof:** đo cùng lúc tại `ddc1a8a`: full run `1696 passed, 26 skipped`;
  `--collect-only` `1719 tests collected`. Ghi ở `docs/PLAN_TCBS_ROUND2.md` §0.
- **Tags:** `pytest`, `collect`, `skip`, `count`, `baseline`, `compare`
- **QUY TẮC:** Chỉ đối chiếu chéo số trong **cùng một lần chạy**. Đổi máy/đổi lần chạy thì
  ghi rõ điều kiện, không so trực tiếp.
- **CHECKLIST:**
  - [ ] Hai con số so sánh có cùng **thời điểm** và **cùng lệnh** không?
  - [ ] Có test nào `skip` ở **mức module** không?
  - [ ] Đã ghi rõ baseline đo ở commit nào, máy nào không?