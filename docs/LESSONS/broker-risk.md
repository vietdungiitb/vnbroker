# Broker Risk — An toàn tiền thật (TCBS / broker lane)

> Nhóm bài học **chỉ có ở repo này**: `vnbroker` nối tài khoản thật — một "chi tiết
> nhỏ" có thể thành **nạp tiền sai** hoặc **báo thành công khi lệnh đã bị từ chối**.
> Đọc nhóm này **bắt buộc** trước mọi thay đổi trong `vnbroker/broker/`.

## L-R01: HTTP 200 KHÔNG đồng nghĩa thành công

- **Sai lầm:** `money.py._post` gọi `resp.json()` rồi trả thẳng cho caller. Không nơi nào
  trong lane broker đọc mã nghiệp vụ. Spec mô tả write endpoint trả `rc`:
  `"1: success, < 0: error"`.
- **Hậu quả thật:** TCBS trả **HTTP 200 kèm `{"rc":"0","rs":"không đủ tiền"}`**. Caller
  nhận về một `dict` bình thường, dễ tưởng lệnh thành công. Với lệnh nộp/rút/chuyển
  margin đây là sai lệch trực tiếp về tiền.
- **Sửa:** thêm `vnbroker/broker/tcbs/_write_http.py::describe_business_code()` và ghi rõ
  vào docstring từng write method. **Cố ý KHÔNG raise tự động** — spec không liệt kê đủ
  tập mã để suy ra "thành công", và chưa có JWT để đo server thật; raise theo tập đoán có
  thể **chặn nhầm một lệnh hợp lệ**.
- **Proof:** `bc9d786`; `docs/REPORT_TCBS_ROUND2.md` §6 R1. Còn nợ khi có JWT: đo tập `rc` thật của `deposit` / `withdraw` / `transfer` / `cancel-condition`.
- **Tags:** `money`, `write`, `rc`, `business-code`, `tcbs`, `idempotency`
- **QUY TẮC:** Mọi write endpoint trả về cho caller phải kèm **cảnh báo tiếng Việt** rằng
  HTTP 200 có thể là thất bại nghiệp vụ. Caller **phải** tự kiểm mã.
- **CHECKLIST:**
  - [ ] Write method mới có ghi cảnh báo `rc` vào docstring không? `describe_business_code(res)` trước khi coi là thành công?
  - [ ] Có test chứng minh HTTP 200 + `rc='0'` **vẫn trả nguyên văn** (không bị nuốt)?

## L-R02: `write_gate` đọc `dry_run` từ `kwargs` ⇒ bắt buộc keyword-only

- **Sai lầm:** `write_gate` (`vnbroker/broker/security/guards.py:46`) đọc
  `dry_run = kwargs.get("dry_run", True)`. Method khai `dry_run` là tham số **vị trí**
  sẽ không bao giờ được gate đọc tới.
- **Hậu quả thật:** `dry_run=False` truyền vị trí ⇒ `kwargs` không có `dry_run` ⇒ gate mặc
  định `True` ⇒ **trả envelope, không gửi lệnh**. Ngược lại nếu ai đó truyền
  `dry_run=False` vị trí với ý định "chạy thật" mà session chưa bật write, hành vi lệch
  khỏi dự kiến của người đọc. Đây là cơ chế bảo vệ tiền — làm hỏng nó tệ hơn là không có.
- **Proof:** đo `inspect.signature` trên 12 write method của đợt 2 (4 public + 4 `_gated_*`
  + 4 facade) ⇒ **12/12 `KEYWORD_ONLY`**, ghi ở `docs/SUMMARY_e-cond-sec.md`.
- **Tags:** `write`, `gate`, `guards`, `signature`, `safety`, `dry-run`
- **QUY TẮC:** Mọi write method **bắt buộc** khai `*, dry_run: bool = True`
  (keyword-only). Ngoài ra phải validate **trước** khi gọi gate.
- **CHECKLIST:**
  - [ ] `dry_run` là **keyword-only**? (kiểm bằng `inspect.signature`, không bằng mắt)
  - [ ] Validation chạy **trước** gate, không sau?
  - [ ] `dry_run=False` khi chưa `session.enable_write()` ⇒ `BrokerPermissionError`?
  - [ ] Test chứng minh **không** gửi HTTP trong cả 2 nhánh? (dùng call counter)

## L-R03: Field null không xuất hiện trong JSON — dùng `.get()`

- **Sai lầm:** Tài liệu `/data-types/` của TCBS: *"Response chỉ chứa các field có giá trị.
  Field null sẽ không xuất hiện trong JSON"*. Đọc field tùy chọn bằng `d["field"]` sẽ
  `KeyError` **đúng lúc server bỏ field**.
- **Hậu quả thật:** Lỗi tương lai không đoán trước được, và nó xảy ra ở lane đọc tiền —
  tức lúc cần dữ liệu nhất. Quan sát thật: response `bars-long-term` còn trả
  `dataT1: null`, không có trong cả 2 tài liệu.
- **Proof:** `docs/PLAN_TCBS_REBUILD.md` (đợt 1) AC S1#4; `docs/REPORT_TCBS_REBUILD.md`
  §1 F2.
- **Tags:** `json`, `get`, `null`, `optional`, `response`, `parse`
- **QUY TẮC:** Mọi field **không** nằm trong `required` của spec phải đọc bằng `.get()`.
  Cột DataFrame dựng từ dict phải có giá trị thay thế tường minh.
- **CHECKLIST:**
  - [ ] Field này có nằm trong `required` của spec không?
  - [ ] Có test với response **thiếu field** không (không `KeyError`)?
  - [ ] Ép kiểu số (`float()`/`pd.to_numeric`) đã xử lý `None` chưa?

## L-R04: `401` chạy trước routing ⇒ không probe được "path còn sống hay không"

- **Sai lầm:** Tưởng có token là probe được 18 path đã gỡ còn sống trên server hay không.
- **Hậu quả thật:** TCBS trả `401` **trước** khi route ⇒ có token hỏng hay hợp lệ đều
  không phân biệt được route có tồn tại. Thêm nữa môi trường SIT
  `openapisit.tcbs.com.vn` **DNS FAIL** (đã đo) ⇒ không có cách nào verify.
- **Proof:** `docs/PLAN_TCBS_ROUND2.md` §1 R3 của đợt 1; `docs/SUMMARY_TCBS_REBUILD.md`
  §6 (mục "Xác nhận 18 path legacy chết trên server").
- **Tags:** `probe`, `401`, `routing`, `unverifiable`, `tcbs`, `legacy`
- **QUY TẮC:** Không viết *"đã xác nhận path không tồn tại"* khi **chưa** probe được.
  Chỉ được viết *"xoá theo quyết định Owner, dựa trên tài liệu, chưa probe server"*.
- **CHECKLIST:**
  - [ ] Kết luận này dựa trên **probe thật** hay trên **tài liệu**?
  - [ ] Đã ghi rõ tầng nào chặn (`401` trước routing) không?
  - [ ] Đã thử môi trường thay thế (SIT/DNS) chưa, kết quả ghi ra sao?

## L-R05: Không tự đặt hạn token khi server không nói

- **Sai lầm:** `auth.py` đọc `data.get("expiredTime")`. Field này **không tồn tại trong
  spec** (đếm **0** lần toàn spec) ⇒ `None` ⇒ `session.set_token(..., expires_at=None)`
  ⇒ `session.py:90` rơi vào nhánh `else` ⇒ `token_expires_at = now + 28800s` — **tự chế
  8 giờ**.
- **Hậu quả thật:** Token chết vẫn được dùng tới 8 giờ ⇒ mọi request sau đó **401 từ
  server**, thay vì `BrokerSessionExpiredError` sạch kèm hướng dẫn ("cần OTP mới").
- **Proof:** `session.py:76,87-90` @ `ddc1a8a`; đo lại trên cây cũ:
  `token_expires_at = now + 8h` (ĐỎ) → cây mới `None` (XANH). Sửa ở `d7d75ca`.
- **Tags:** `auth`, `token`, `jwt`, `exp`, `ttl`, `session`, `tcbs`
- **QUY TẮC:** Khi server **không** nói hạn, **không bịa** — để `None` (không biết) và để
  **caller** quyết định. `TokenManager.is_expired()` trả tri-state `True/False/None`.
- **ĐÍNH CHÍNH (2026-10-10):** "8 giờ"/28800 **sai ngay từ đầu** — đo JWT thật:
  `exp - iat = 86400s = 24.0 giờ`. Tài liệu TCBS ghi "~8 giờ" là **suy đoán, chưa đo**.
  Đã sửa `session.py` + 9 chỗ `docs/`, thêm `TCBS_JWT_TTL_SECONDS = 86400`. Cùng bậc L-E01: **số trong tài liệu ≠ số đo**. (DNSE — broker khác — để nguyên.)
  - [ ] Field hạn lấy từ đâu — có **thực sự** trong spec không?
  - [ ] Không decode được thì có **không** rơi về giá trị mặc định bịa không?
  - [ ] `session.py` có nhánh fallback `expires_in_seconds=28800` không?
  - [ ] Đã kiểm JWT `exp` là **nguồn duy nhất**; buffer lấy từ hằng `BrokerSession`?

## L-R06: Mọi HTTP 4xx ở write path phải map thành `BrokerError`

- **Sai lầm:** `_check_status` của `money.py` chỉ map `401`/`403`/`>=500`, nên `400` `404`
  `422` `429` **rơi qua** và `resp.json()` trả về như thành công. Cùng đợt,
  `condition_orders.py` map **đủ** ⇒ hai write path khác nhau trong cùng thư viện.
- **Hậu quả thật:** Server trả 422 "không đủ tiền" → caller nhận dict trông bình thường →
  tạo cảm giác an toàn giả, tệ hơn không có write endpoint.
- **Proof:** `bc9d786`; đo trên `money.py` bản cũ `90ead64`: 4/4 test **`DID NOT RAISE`**
  cho `400/404/422/429`; sau sửa 32/32 xanh. Helper: `broker/tcbs/_write_http.py` (155L).
- **Tags:** `write`, `status`, `4xx`, `error-mapping`, `money`, `_write_http`
- **QUY TẮC:** Write path phải map **mọi** `>= 400` thành exception. AC nên có cho mọi
  lát có write endpoint: *"mọi HTTP 4xx/5xx phải raise `BrokerError`, không trả body lỗi"*.
- **CHECKLIST:**
  - [ ] Bảng map status → exception **đầy đủ**, không bỏ trống mã nào?
  - [ ] Test parametrized cho **từng** mã lỗi, và lỗi không có body JSON vẫn raise?
  - [ ] Các write path khác trong repo có map **giống nhau** không?

## L-R07: Đừng để công cụ gợi ý "sửa" theo hướng mất tiền

- **Sai lầm:** Cổng đối chiếu payload báo `pinCode -> spec gọi là price` (heuristic
  trùng 4/5 ký tự). Người đọc làm theo sẽ **gửi PIN giao dịch vào ô giá**.
- **Hậu quả thật:** Lỗi gốc chỉ là gửi thừa 1 field không có trong spec. Bản "sửa"
  theo gợi ý sai là **mất tiền thật**. Công cụ **gây ra** lỗi nguy hiểm hơn lỗi nó
  phát hiện.
- **Proof:** `scripts/check_tcbs_bodies.py` sửa ở `ee0fbc5` —
  `_looks_semantically_different()` không gợi tên thay thế khi tên chứa `pin`; `price`
  vẫn bị bắt bằng đường `MISSING required`.
- **Tags:** `money`, `pin`, `field name`, `heuristic`, `gate`, `dangerous`, `write`
- **QUY TẮC:** Gợi ý của cổng **phải là điều người đọc không thể hành động sai**. Khi
  tên trùng ký tự nhưng **nghĩa khác** ⇒ chỉ báo lệch, **không** đề xuất đổi tên.
- **CHECKLIST:**
  - [ ] Gợi ý nào của cổng có thể gây **sai sót mới**?
  - [ ] Field nhạy cảm (`pin` `otp` `api_key` `password`) có bị gợi ý đổi tên không?
  - [ ] Phân biệt được "sai chính tả" (`orderId`↔`orderNo`) với "khác nghĩa" (`pinCode`↔`price`) không?
