# PHỤ LỤC A — Đối chiếu với `docs/LESSONS/` của chính repo `vnbroker`

**Ngày:** 2026-10-11 · **Bổ sung cho:** `docs/PROPOSAL_VNINVEST_REQUIREMENTS_20261011.md`
**Đọc sau tài liệu đề xuất chính.** Phụ lục này **sửa lại** hai chỗ trong đề xuất và bổ sung một phát hiện mang tính hệ thống.

---

## A.0. Kết luận ngắn

Tôi đã đọc `docs/LESSONS/` **sau khi** viết đề xuất chính. Đây là sai thứ tự, và nó dẫn tới một sai sót.

**Sai sót:** `WP-05` của tôi yêu cầu *"gọi `describe_business_code()` và raise"*. Điều đó **mâu thuẫn với một quyết định có chủ ý đã ghi bằng văn bản** — xem A.2.

**Phát hiện lớn hơn nhiều:** `docs/LESSONS/` của repo này là tài sản **tốt nhất** tôi gặp ở hai repo. Nhưng chúng **mục rút**. L-R06 đã viết rõ *"Server trả 422 'không đủ tiền' → caller nhận dict trông bình thường"*, có đo đạc, có proof — và **đường đặt lệnh chính vẫn còn đúng lỗi đó**.

---

## A.1. ⭐ Phát hiện mang tính hệ thống: **lesson mục rút, vì không có cơ chế cưỡng chế**

`docs/LESSONS/` ghi 4 nhóm: `broker-risk.md` (L-R01..07), `gate-integrity.md` (L-G01..04), `evidence.md`, `process.md`. Chất lượng rất cao — mỗi lesson có **Proof** (commit hash, số đo trước/sau), **Tags**, **CHECKLIST** kiểm được.

Vấn đề: **lesson chỉ tồn tại dưới dạng văn bản**. Không có đường nào nối từ lesson → gate. Bằng chứng:

### Bằng chứng 1 — L-R06 đã học, đã đo, và **mục rút ở file quan trọng nhất**

`broker-risk.md:102-117` (L-R06): *"Mọi HTTP 4xx ở write path phải map thành `BrokerError`"*, kèm proof *"đo trên `money.py` bản cũ `90ead64`: 4/4 test **DID NOT RAISE** cho `400/404/422/429`; sau sửa 32/32 xanh"*.

Helper được tạo ra để chống lại đúng điều đó — `_write_http.raise_for_status`, map **7** mã:

```python
# broker/tcbs/_write_http.py:46-87
401 → BrokerAuthError
403 → BrokerPermissionError
400 → BrokerValidationError
422 → BrokerOrderError          ← có
404 → BrokerValidationError     ← có
429 → BrokerRateLimitError
>=500 → BrokerNetworkError
```

Nhưng **đường đặt lệnh chính không dùng helper đó**:

```python
# broker/tcbs/equity.py:409-441  — _write_request, dùng cho place_order/modify_order/cancel_order
if resp.status_code == 401: ...   ✓
if resp.status_code == 403: ...   ✓
if resp.status_code == 429: ...   ✓
if resp.status_code == 400: ...   ✓
if resp.status_code >= 500: ...   ✓
                                ✗ 422 rơi xuống đây
                                ✗ 404 rơi xuống đây
return resp.json()          ← dòng 441
```

**Đo lại 3 write path trong cùng một thư viện:**

| Write path | 401 | 403 | 400 | **404** | **422** | 429 | 5xx |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `money.py` (qua `raise_for_status`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `condition_orders.py` (qua `raise_for_status`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **`equity.py::_write_request`** | ✓ | ✓ | ✓ | **✗** | **✗** | ✓ | ✓ |

**Hậu quả cụ thể:** TCBS trả `422` khi đặt lệnh (ví dụ không đủ tiền) → `equity.py` không map → `resp.json()` trả thẳng cho caller. **Đúng kịch bản L-R06 mô tả, trên file L-R06 không nói đến.**

Và nó cộng dồn với L-R01: `422` trả về thân `"không đủ tiền"` ⇒ caller nhận `dict` bình thường có vẻ thành công.

### Bằng chứng 2 — L-R02 đã áp cho TCBS, **không áp cho DNSE**

`broker-risk.md:27-45` (L-R02): *"Mọi write method **bắt buộc** khai `*, dry_run: bool = True` (keyword-only)"*, proof *"12/12 `KEYWORD_ONLY`"*.

Đo bằng `inspect.signature` trên lane DNSE (`connector/dnse/trade.py`):

| Method | `dry_run` kiểu | default |
|:--|:--|:-:|
| `place_order`, `cancel_order`, `deposit_derivative_margin`, `withdraw_derivative_margin` | POSITIONAL | `True` |
| `cancel_conditional_order`, `close_deal`, `place_conditional_order`, `set_account_pnl_config`, `set_deal_pnl_config` | POSITIONAL | **`False`** |

⇒ **5/9 method DNSE vi phạm đúng L-R02.** Đây **không phải bypass** (`_write_enabled` khởi tạo `False`, `_require_write` chặn, test `test_write_requires_explicit_enable_write` PASS) — nhưng sau `enable_write()`, 5 method này **tự gửi thật** trong khi 4 method kia vẫn phải truyền `dry_run=False` tường minh.

Và `test_write_safety.py::WRITE_METHODS` chỉ liệt kê **4** method ⇒ lane mới sinh ra **không có test phủ** luật L-R02.

**Mẫu lặp:** lane TCBS sinh ra 12 method, lesson viết sau đó. Lane DNSE sinh ra 9 method **sau**, không ai chạy lại checklist.

### Bằng chứng 3 — L-G02 ("mọi gate phải có test khoá phạm vi") chưa được áp cho chính cổng payload

`gate-integrity.md:25-47` (L-G02): *"Mọi gate phải có **test khoá phạm vi** (`assert len(...) == N` kèm danh sách file)"*.

Nhưng `scripts/check_tcbs_bodies.py` **chỉ quét `broker/tcbs/`**. Độ phủ thật:

| Lane | Số write method | Cổng payload |
|:--|:-:|:-:|
| `broker/tcbs/` | 12 | ✓ |
| `broker/ssi/` (5 method, 1 ký RSA) | 5 | **0** |
| `connector/dnse/trade.py` | 9 | **0** |
| `brokerage/tcbs/client.py` | 3 | **0** |

⇒ 17/29 write method trong thư viện **không qua cổng nào**.

**Đây chính xác là lỗi L-G02 mô tả** — *"lỗi tệ nhất: không có tín hiệu nào"* — chỉ là nó xảy ra ở **phạm vi** (lane) thay vì ở ** cú pháp** (`AnnAssign` vs `Assign`).

### Kết luận

> Lesson ở repo này **đúng và đã được đo**. Nhưng lesson không có **cái giá khi không tuân thủ**. Ba ví dụ trên là cùng một cơ chế: **thêm một lane / một file mới ⇒ checklist cũ không tự áp**.

---

## A.2. 🔧 Sửa lại `WP-05` — tôn trọng quyết định có chủ ý, và nói rõ blocker đã gỡ

`broker-risk.md:15-22` (L-R01) ghi **cố ý không raise**:

> *"thêm `describe_business_code()` và ghi rõ vào docstring từng write method. **Cố ý KHÔNG raise tự động** — spec không liệt kê đủ tập mã để suy ra 'thành công', và **chưa có JWT để đo server thật**; raise theo tập đoán có thể **chặn nhầm một lệnh hợp lệ**."*

**Tôi đã đọc điều này quá muộn. Yêu cầu "raise" trong `WP-05` của tôi là không đúng — nó bỏ qua một ràng buộc đã suy nghĩ kỹ.**

Nhưng có một điều quan trọng: **blocker mà lesson nêu — "chưa có JWT" — không còn đúng.**

`docs/CLAIMS.md`, mục **TCBS Round 4 (2026-10-10)**:

> *"**Phát hiện lớn nhất:** `.env` **ĐÃ CÓ JWT** (1290 ký tự, còn hiệu lực đến 19:10). 4 đợt trước đều ghi 'chưa có JWT' — sai, chỉ là chưa ai mở `.env` kiểm."*

Và `CHANGELOG.md`, mục Round 4, khối **CHƯA CHẠY** vẫn liệt kê: *"đo tập `rc`"*.

⇒ **Ràng buộc đã gỡ, nhưng nợ chưa đóng.** Đây là đề xuất cụ thể nhất tôi đưa ra được:

### `WP-05` (đã sửa) — Đo tập mã nghiệp vụ thật, rồi mới quyết raise hay không

**AC (theo đúng thứ tự, mỗi bước là một commit):**

- [ ] **B-1.** Với JWT trong `.env`, đo `rc`/`error`/`code` thật của `deposit`, `withdraw`, `transfer`, `cancel-condition`, `place_order`. Ghi bảng kết quả vào `docs/TCBS_BUSINESS_CODES.md`, kèm **ngày đo** và **endpoint**.
- [ ] **B-2.** Đối chiếu: mỗi endpoint family dùng quy ước nào? Hiện đang **không nhất quán** — `money.py` spec ghi `"1: success, < 0: error"`, còn `equity_orders.py:70-71` docstring ghi `{'error': '0'}` = thành công. **Ghi rõ quy ước cho từng family**, không gộp.
- [ ] **B-3.** Chỉ sau khi có bảng: `raise` cho mã **chắc chắn là lỗi** (có bằng chứng đo). Mã **chưa biết** ⇒ `raise BrokerOrderError` với message *"mã nghiệp vụ chưa được phân loại: {code}"* — **không** coi là thành công.
- [ ] **B-4.** Trong lúc chờ đo xong: caller **bắt buộc** phải đọc `business_code`. Nhưng thay vì ghi trong docstring (**bắt buộc không ai đọc** — L-R01 đã tự nhận điều này), **trả về một object có `.ok`** mà `.ok` chỉ `True` khi mã khớp tập đã đo. Không đo được ⇒ `.ok = None` (không phải `True`).
- [ ] **B-5.** Thêm vào `VERSION_NOTICES` một mục: **thay đổi kiểu trả về của write method**. Đây là breaking change phải công bố, vì `dict` → object có thuộc tính.

**Cách làm B-4 là điểm mấu chốt:** nó thỏa mãn đồng thời L-R01 (*"không raise theo tập đoán"*) và yêu cầu của tôi (*"caller không được nhầm thất bại với thành công"*) — vì `.ok` **không bao giờ là `True` khi chưa biết**.

### Bổ sung cho A.1 — `WP-05` mới còn phải gồm phần sửa drift L-R06

Độc lập với câu chuyện `rc`, cái đã đo ở A.1 là **lỗi chắc chắn** và **không có ràng buộc nào ngăn cản**:

> **`equity.py::_write_request` phải gọi `raise_for_status()` của `_write_http.py`, hoặc copy đủ 7 nhánh.**

Bản `raise_for_status` không đoán gì — nó chỉ map **HTTP status**, không đụng mã nghiệp vụ. Rủi ro "chặn nhầm lệnh hợp lệ" mà L-R01 lo là **không áp dụng** ở đây: `404` là *endpoint không tồn tại*, `422` là *lệnh bị broker từ chối* — cả hai đều không phải lệnh hợp lệ.

- [ ] `equity.py::_write_request` dùng chung `raise_for_status`
- [ ] Test parametrized: `404`, `422` ⇒ raise; và **3** write path (`money` / `condition_orders` / `equity`) có **cùng** bảng map ⇒ test dùng chung, không copy 3 lần
- [ ] Đóng nợ **N8** mà `CHANGELOG.md` đã ghi nhận là "hệ quả cụ thể thì chưa ai đóng"

---

## A.3. Đề xuất cơ chế cưỡng chế (thay cho việc "nhớ đọc lesson")

Lesson không tự áp dụng. Không có cơ chế nào khiến nó tự áp dụng. Đề xuất 3 tầng, theo đúng tinh thần L-G01/L-G02 (đừng tin, hãy **cưỡng chế**):

### Tầng 1 — Checklist thành test

Mỗi dòng CHECKLIST trong `docs/LESSONS/` phải có **ít nhất một** test hoặc một dòng của `check_*.py`. Nếu không ánh xạ được ⇒ lesson đó là **văn bản trang trí**, và phải ghi rõ như vậy.

| Lesson | CHECKLIST | Nơi kiểm hôm nay | Trạng thái |
|:--|:--|:--|:--|
| L-R01 | kiểm `rc` trước khi coi là thành công | **không có** | 🔴 văn bản trang trí |
| L-R02 | `dry_run` keyword-only, kiểm bằng `inspect.signature` | `test_write_safety.py` — **4/9 method DNSE** | 🔴 phủ một nửa |
| L-R03 | đọc field tùy chọn bằng `.get()` | không rõ | 🟡 |
| L-R05 | không rơi về hạn bịa | `session.py` đã sửa | 🟢 |
| L-R06 | map **mọi** 4xx thành `BrokerError` | `equity.py` thiếu 404/422 | 🔴 mục rút |
| L-G01 | self-test bắt exit code thật | `check_all.ps1` đã sửa | 🟢 |
| L-G02 | gate có test khoá phạm vi | có, nhưng **chỉ 1 lane** | 🟡 |

### Tầng 2 — Ratchet: số N phải **đóng băng trong test**

Đúng như L-G02 yêu cầu, mở rộng ra **toàn bộ số liệu**:

```python
# Ý tưởng — chưa đề xuất tên file cụ thể
assert set(DRY_RUN_METHODS) == {  # đóng băng, thêm method mới ⇒ test ĐỎ
    "place_order", "cancel_order", ...
}
assert all(sig.parameters["dry_run"].kind == KEYWORD_ONLY for ...)
assert all(sig.parameters["dry_run"].default is True for ...)   # bắt cả default=False
```

Và cho **mọi write path**:

```python
STATUS_MAP = {401, 403, 400, 404, 422, 429, "5xx"}   # đóng băng
# test: mọi write path phải map ĐÚNG tập này — thiếu một là đỏ
```

### Tầng 3 — Mở rộng cổng payload sang SSI + DNSE + brokerage

- `scripts/check_tcbs_bodies.py` **lấy tên chung** (hiện tên gắn chặt vào `tcbs`) và quét cả 3 lane còn lại.
- Hoặc tốt hơn: **một test đếm write method trên toàn repo** và assert bằng danh sách — thêm method mới mà không có trong danh sách ⇒ đỏ. Đây là hình thức rẻ nhất để bắt đúng lỗi "lane mới không qua cổng".

### Tầng 4 (quy trình) — `CLAIMS.md` ghi cả **lesson đã áp chưa**

Mỗi mục claim hiện ghi gate đã chạy (`8/8 PASS`, `tcbs-bodies 0 lech`). Nên thêm một dòng:

> **Lesson áp dụng:** L-R0x — **ĐÃ ÁP / CHƯA ÁP** (với lý do nếu chưa)

Làm vậy thì chính `CLAIMS.md` trở thành bảng theo dõi lesson, thay vì phải đi tra 4 file lesson để biết điều gì còn nợ.

---

## A.4. Những chỗ tôi đã viết quá chắc trong đề xuất chính

| Chỗ | Bản gốc | Sửa thành |
|:--|:--|:--|
| `WP-05` | "kiểm mã nghiệp vụ rồi **raise**" | **Đo trước** (đã có JWT), `.ok = None` khi chưa biết, chỉ raise mã **đã đo chắc chắn**. Tôn trọng L-R01. |
| `BL-5` (idempotency) | "bật `IdempotencyStore` thật" | Giữ nguyên, nhưng bổ sung: TCBS **không có** dedupe phía server (spec `POST /akhlys/.../orders` không có `requestId`) ⇒ dedupe buộc phải ở client. Không thể đẩy xuống broker. |
| `MA-19` ("TCBS không chặn `price==0` cho LO") | nêu như thiếu sót | Giữ nguyên, nhưng ghi rõ **SSI đã làm đúng** (`broker/ssi/equity.py:424-430`) ⇒ đây là **drift giữa 2 lane**, không phải thiếu sót chung. L-R02/L-R06 đã làm mẫu. |
| `§7` (đừng phá) | chưa có | Bổ sung: `docs/LESSONS/` **là hạ tầng chất lượng thật** — 24 lesson có Proof và số đo, mạnh hơn bất kỳ tài liệu kiểu đó tôi gặp. Đừng viết lại từ đầu. |

---

## A.5. Câu hỏi bổ sung cho đội `vnbroker`

| # | Câu hỏi | Vì sao chặn |
|:--|:--|:--|
| Q8 | Ai giữ `docs/LESSONS/`? Có ai đọc trước khi **viết method mới** không, hay chỉ đọc trước khi **sửa** `vnbroker/broker/`? | Nếu chỉ đọc khi sửa thì lane mới (như DNSE) sẽ tiếp tục mục rút. |
| Q9 | `CHANGELOG.md` Round 4 ghi *"CHUA CHAY: đo tập `rc`"*. Vì sao chưa đo khi đã có JWT? | Đây là **nợ duy nhất** chặn L-R01. Cần biết có rào cản kỹ thuật hay là chưa ai quay lại. |
| Q10 | 17/29 write method ngoài phạm vi cổng payload — **cố ý** hay chưa tới? | Nếu cố ý thì phải ghi vào lesson là ngoại lệ có lý do; nếu chưa tới thì đây là rủi ro đã biết chưa được ghi. |
| Q11 | `equity.py::_write_request` tồn tại vì lý do gì (legacy, trước khi có `_write_http.py`)? | Biết được sẽ chọn: refactor gộp, hay chỉ vá bảng map. |

---

*Bổ sung vào đề xuất chính. Hai tài liệu nên đọc cùng nhau, theo thứ tự: đề xuất chính → phụ lục này.*