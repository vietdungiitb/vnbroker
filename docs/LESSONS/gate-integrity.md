# Gate Integrity — Cổng nói "PASS" nhưng không kiểm tra đủ

> Nhóm bài học về **cổng chặn tự nó**. Ở repo này đã có 4 lần cổng báo xanh
> trong khi **không hề kiểm tra** thứ cần kiểm — và 3 lần đó do chính tôi viết
> cổng trong cùng phiên.

## L-G01: Self-test không ép = dòng "phải xanh" chỉ là chữ

- **Sai lầm:** `check_all.ps1` chạy self-test của các gate mới rồi **in** kết quả,
  nhưng: `& $st.cmd 2>&1 | Select-Object -Last 1` — không đọc `$LASTEXITCODE`, không
  đếm lỗi, không `exit 1`.
- **Hậu quả thật:** Self-test hỏng thì gate đó im lặng. Dòng comment trong chính
  script ghi *"phải xanh"* trong khi không có gì ép nó xanh.
- **Proof:** phá self-test (`if False:` trong `check_lessons.py`) ⇒ trước khi sửa:
  `check_all -Quick` **exit 0** với self-test hỏng. Sau khi sửa:
  `FAIL: 1 self-test gate that FAIL`, **exit 1** @ `ee0fbc5`.
- **Tags:** `gate`, `self-test`, `exit code`, `PowerShell`, `enforce`, `check_all`
- **QUY TẮC:** Mọi self-test phải **bắt exit code thật**, đếm lỗi, và `exit 1` khi
  có lỗi. In kết quả **không** phải là ép. Không pipe qua filter rồi mất `$LASTEXITCODE`.
- **CHECKLIST:**
  - [ ] Self-test có đọc `$LASTEXITCODE` không?
  - [ ] Có biến đếm fail và `exit 1` không?
  - [ ] Đã **phá** self-test để chứng minh nó đỏ không? (chạy 1 lần, ghi kết quả)

## L-G02: Cổng bỏ sót mà vẫn báo xanh — im lặng còn nguy hiểm hơn báo sai

- **Sai lầm:** `check_tcbs_bodies.py` bỏ sót **4/12** write method, và vẫn exit 0.
  Ba lỗi phủ, tìm ra bởi audit độc lập:
  1. `money.py`/`condition_orders.py` gán payload bằng **có annotation**
     (`payload: dict = {...}` ⇒ `ast.AnnAssign`), cổng chỉ bắt `ast.Assign`.
  2. Không xử lý `node.keywords` ⇒ bỏ sót `self._post(url, payload=payload)`.
  3. Đếm luôn `_post`/`_put` (tầng HTTP, payload rỗng) làm nhiễu danh sách.
- **Hậu quả thật:** Phủ 8/12. 4 method bị bỏ sót **đang đúng spec**, nên lỗi là
  *tiềm ẩn* — ngày ai đó viết sai payload ở đó, cổng không kêu. Đây là loại lỗi
  tệ nhất: **không có tín hiệu nào**.
- **Proof:** đo trước/sau @ `ee0fbc5`: `payload write tim thay: 8` → **`12`**;
  4 method mới tìm ra đều **0 lệch** ⇒ xác nhận code round 2 đúng spec.
  Khoá bằng `test_gate_tim_thay_du_12_write_method` + `test_gate_bat_duoc_kwarg_payload`.
- **Tags:** `gate`, `coverage`, `AST`, `AnnAssign`, `keywords`, `blind spot`
- **QUY TẮC:** Mọi gate phải có **test khoá phạm vi** (`assert len(...) == N` kèm
  danh sách file). Gate quét AST **bắt cả `Assign` và `AnnAssign`**, và cả
  **positional lẫn keyword**. Số N **đóng băng trong test** để lệch phải đỏ.
- **CHECKLIST:**
  - [ ] Gate có test khoá **phạm vi** (số phần tử + danh sách file) không?
  - [ ] Có xử lý `AnnAssign`, `keywords`, `ast.walk` đệ quy trên dict lồng không?
  - [ ] Có loại trừ helper/tầng HTTP để không đếm nhầm không?
  - [ ] Khi thêm 1 mục mới vào nguồn, test phủ có **đỏ** để buộc cập nhật không?

## L-G03: Baseline khoá quá thô = xanh giả có đường vòng

- **Sai lầm:** Baseline ban đầu khoá theo `KIND + file + method` — **không** kèm
  tên field. Thêm một field sai **mới** vào một method đã bị gắn cờ thì **lọt qua im
  lặng**.
- **Hậu quả thật:** Nợ cũ được tha, nhưng lỗi mới trong đúng method đó vẫn qua.
  Đây là dạng "xanh giả có đường vòng" — tệ hơn không có baseline.
- **Proof:** fail-trước: thêm `totallyBogusField` vào `_gated_cancel_derivative_order`
  ⇒ `lech moi: 0`, **exit 0**. Sau khi khoá kèm tên field ⇒ `lech moi: 3`, **exit 1**.
- **Tags:** `gate`, `baseline`, `ratchet`, `waiver`, `false green`, `spec`
- **QUY TẮC:** Khoá baseline ở **mức tối thiểu có nghĩa**: `(loại lệch, file, method,
  **tên field**)`. Sinh baseline bằng `--write-baseline`, **không** viết tay.
  Bỏ 1 dòng baseline ⇒ gate phải đỏ lại (thử, không giả định).
- **CHECKLIST:**
  - [ ] Khoá baseline có đủ tên field không, hay chỉ tên method?
  - [ ] Baseline **sinh bằng lệnh** hay gõ tay?
  - [ ] Đã thử **xoá 1 dòng** baseline để chứng minh gate đỏ lại?
  - [ ] Thêm field sai mới vào method **đã có cờ** → gate có đỏ không? (phải đỏ)

## L-G04: Gợi ý sai còn nguy hiểm hơn lỗi gốc

- **Sai lầm:** Heuristic tên field đề xuất `pinCode -> spec gọi là price`
  (4/5 ký trùng). Người đọc baseline rồi "sửa cho khớp" sẽ **gửi PIN giao dịch vào
  ô giá**.
- **Hậu quả thật:** Lỗi gốc là gửi thừa 1 field vô hại; "bản sửa" theo gợi ý sai
  là **mất tiền**. Gate đã **gây ra** lỗi mới.
- **Proof:** đo ratio 4/5 = 0.800 đúng ngưỡng ⇒ hiện ra `SUSPECT` @ `93a89e8`;
  sửa ở `ee0fbc5` (chỉ báo `EXTRA`, không gợi tên thay thế khi tên chứa `pin`).
- **Tags:** `gate`, `heuristic`, `false positive`, `money`, `dangerous`, `field name`
- **QUY TẮC:** Cổng **được phép** đưa gợi ý, nhưng gợi ý **phải là điều người đọc
  không thể hành động sai**. Khi tên trùng ký tự nhưng **nghĩa khác**, chỉ báo lệch,
  **không** đề xuất đổi tên.
- **CHECKLIST:**
  - [ ] Gợi ý của gate có thể gây **sai sót mới** không?
  - [ ] Field nhạy cảm (`pin` `otp` `api_key` `password`) có bị gợi ý đổi tên không?
  - [ ] Gợi ý có phân biệt "sai chính tả" với "khác nghĩa" không?