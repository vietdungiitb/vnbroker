# AUDIT — Tier-1 Wave 1 + Wave 2 (đợt 2026-10-10)

**Cây:** `feat/tier1-wave12` @ `a907b83` (base `9d5db1d`)
**Phương pháp:** 2 vòng audit **read-only độc lập** + tự kiểm lại bằng script của
tác giả (L-P05: lời agent là lời người khác; phải đo lại).
**Lessons áp dụng:** L-E01 · L-E04 · L-E05 · L-E06 · L-P03 · L-P05

---

## 1. Kết luận

| Mốc | Kết quả |
|:--|:--|
| blocker còn lại | **0** |
| major còn lại | **0** |
| minor còn lại | 0 trong phạm vi sửa; 3 ghi nhận mở ở §5 |
| `confidence:` | **high** cho mọi phát hiện đã đóng — đều tái lập được bằng lệnh ghi kèm |

Cả hai vòng audit đều **ban đầu trả về lỗi**, và mọi lỗi đều đã sửa + thêm test
khoá lại. Không có phát hiện nào bị bác bỏ mà không có lý do.

---

## 2. Vòng 1 — audit Wave 2 (chuẩn hoá)

Tác giả: agent độc lập, read-only. Kết quả: **1 blocker · 1 major · 3 minor**.

| ID | Mức | Vấn đề | Bằng chứng | Trạng thái |
|:--|:--|:--|:--|:--|
| **A1** | **blocker** | Bản sửa `api/quote.py` là **DEAD CODE**. `history`/`intraday` có `@dynamic_method` (`base.py:21`); decorator rẽ sang `_call_dynamic_method` **trước khi thân hàm chạy** ⇒ `self._normalize(...)` không bao giờ chạy. | Script tự kiểm: `_delegate_to_provider` gọi **0** lần; kết quả là frame thô của provider (`datetime64[s]`, `match_type=['buy']`). **Tác giả tự tái lập lại và xác nhận.** | ✅ Đã sửa `06d7e4f` — thêm hook `_post_process_result` trên `BaseAdapter`, gọi từ `_invoke_provider_method` (điểm mọi lời gọi provider đều đi qua). Test khoá: `test_api_quote_adapter_normalizes_even_though_body_is_dead_code` |
| **A2** | major | `_to_canonical_tz` chỉ `localize` khi thiếu tz ⇒ frame `datetime64[ns, UTC]` lọt qua, trái hợp đồng, và `concat` với frame VN ra `object` | `ohlc_to_df` nhánh `else` (`transform.py:379`) giữ nguyên UTC từ chuỗi provider | ✅ Đã sửa `06d7e4f` — tz vùng khác thì `tz_convert` (giữ mốc thời gian), không `tz_localize`. Test: `test_utc_aware_frame_is_converted_not_left_alone`, `test_other_offsets_are_converted_too` |
| **A3** | minor | Timestamp ngoài phạm vi `ns` lọt đơn vị lệch ⇒ `concat` ném `OutOfBoundsDatetime` | Năm 3000 → `[us]` còn frame khác `[ns]` | ✅ Đã sửa `06d7e4f` — dòng vượt biên thành `NaT`, bị bộ lọc sẵn có loại |
| **A4** | minor | `_normalize_match_type` mutate frame của người gọi | Sửa tại chỗ `df["match_type"] = …` | ✅ Đã sửa `06d7e4f` — `assign` trả frame mới |
| **A5** | minor | Hợp đồng thiếu ca cho A2/A3 | Gate xanh trong khi hợp đồng bị vi phạm | ✅ Đã sửa `06d7e4f` — thêm 5 test |

**Claim được xác nhận đúng:** Normalizer là nguồn sự thật duy nhất (traversal, không
đọc bằng mắt); đơn vị lưu trữ thống nhất; `match_type` thống nhất và idempotent,
khác `process_match_types` **duy nhất** ở ATO/ATC (có chủ ý, đã ghi); `market_cap`
bất biến theo đơn vị giá.

---

## 3. Vòng 2 — audit Wave 1 (provider discovery)

Tác giả: agent độc lập, read-only. Kết quả: **0 blocker · 7 major · 4 minor**.

| ID | Mức | Vấn đề | Bằng chứng | Trạng thái |
|:--|:--|:--|:--|:--|
| **F1** | major | Bản sửa W1.3 **không có tác dụng gì**: TCBS khai hỗ trợ 5 module, **cả 5 đều đã có mục** trong `OPEN_SOURCE_CANDIDATES` ⇒ bản "chỉ lấp chỗ trống" không bao giờ chạy. Đo: `tcbs_in_auto=False` ở cả 10 module. | **Tác giả tự tái lập:** `TCBS supports: 5/5 đã có trong bảng` → `AUTO … tcbs_in_auto=False` × 10 | ✅ Đã sửa `80cdd2e` — provider có credential **nối cuối** mọi module, không chen, không đổi thứ tự. Đo lại: `AUTO quote = ['vci','kbs','dnse','tcbs']` |
| **F2** | major | Gate im lặng khi provider có credential bị lo khỏi AUTO (gate chỉ kiểm pool) | Xoá `tcbs` khỏi bảng ưu tiên → gate exit 0 | ✅ Thêm quy tắc **C5** (pool phục vụ được provider nào thì AUTO phải có). Đã **phòng thủ**: inject lại lỗi F1 → gate exit 1 |
| **F3** | major | Xoá hẳn một provider khỏi `AUTH_PROVIDERS` là gate im lặng (C1 duyệt chính danh sách đó) | Gate exit 0, 0 findings | ✅ Thêm quy tắc **C4**. Đã phòng thủ: inject lại → exit 1 |
| **F4** | major | Gate **báo nhầm** trên cấu hình đúng: `available` hardcode `get_available_providers("quote")` | Provider chỉ phục vụ `news` bị báo vi phạm | ✅ Bỏ kiểm tra `quote` cứng; quy tắc per-module phủ hết |
| **F5** | major | `env_all` tính rồi bỏ qua (ruff `F841`); không quy tắc nào bắt dạng chuỗi | `env_all='DNSE_API_SECRET'` (str) ⇒ provider biến khỏi pool im lặng | ✅ C0 kiểm **cả hai**; thêm `scripts` vào phạm vi `ruff-src` (trước đó `scripts/` không được lint — F841 chính vì vậy mà không ai thấy) |
| **F6** | major | Cấu hình hỏng làm gate **ném traceback** thay vì báo lỗi | Bỏ khoá `env_all` → `GATE CRASHED: KeyError` | ✅ Báo có đường dẫn; `main()` bắt mọi lỗi. Đã phòng thủ: inject lại → exit 1 |
| **F7** | major | Máy không có `.env` (mọi clone mới): gate exit 2 ⇒ dòng tóm tắt `FAIL provider-consistency exit=2 OK: khong co vi pham nao.` | Script PowerShell tái lập nguyên dòng đó | ✅ Thiếu `.env` chỉ là **cảnh báo**, vẫn exit 0; reserve exit 2 cho "gate không chạy được"; thêm trạng thái `CHUA CHAY` trong `check_all.ps1` |
| **F8** | minor | Thứ tự provider không tất định (sắp theo hash của `set`) | 5 thứ tự khác nhau / 12 lần chạy chỉ khác `PYTHONHASHSEED` | ✅ Sắp theo thứ tự khai báo rồi theo tên |
| **F9** | minor | Docstring mô tả thứ tự ưu tiên 3 tầng không tồn tại trong code | Đọc source + xác nhận `_gap_fill` trả `[]` cho cả 6 module | ✅ Docstring viết lại đúng những gì code làm |
| **F10** | minor | `--self-test` xoá `TCBS_JWT_TOKEN` của tiến trình gọi | `before=True after=False` | ✅ Lưu/kho�� phục **đầy đủ** danh sách biến bị đụng |
| **F11** | minor | `--self-test` không được `check_all.ps1` chạy | `new gate in SELF-TEST list: False` | ✅ Đã wire vào khối self-test |

**Claim được xác nhận đúng:** `resolve_auth_token` ưu tiên JWT — **17/17** ca biên,
không ca nào trả non-JWT khi JWT hợp lệ, không ca nào bỏ sót JWT. Không còn mã
đọc `env_key`/`env_secret` (chỉ còn văn xuôi trong `docs/`).

---

## 4. Lỗi thứ 5 — phát hiện khi kiểm chứng bằng dữ liệu thật

Không do audit nào tìm ra. Tìm ra khi chạy lại `Vnbroker(source='TCBS')` trên dữ
liệu thật sau khi tất cả audit đã đóng:

`common/client.py:137-140` đọc thẳng `TCBS_AUTH_TOKEN` và truyền xuống làm
`auth_token`, **ghi đè** kết quả của `resolve_auth_token()`. Đo:

```
resolve_auth_token()                     -> len 1290   (JWT thật)
StockComponents.auth_token               -> len 48     (mà server 401)
Vnbroker(source='TCBS').stock('TCB').quote.history()  -> ConnectionError
explorer.tcbs.quote.Quote('TCB').history()           -> 20 dòng
```

Cùng máy, cùng token, hai kết quả. ✅ Đã sửa `a907b83` + 6 test khoá.

**Bài học quy trình (Stage 8):** nếu chỉ kiểm bằng cách gọi provider trực tiếp
thì lỗi này không bao giờ lộ — đường công khai là đường khác. Cần một vòng kiểm
chứng bằng **đúng API mà người dùng gọi**.

---

## 5. Ghi nhận mở (không phải lỗi của đợt này)

| # | Nội dung | Vì sao không sửa ở đây |
|:--|:--|:--|
| **O1** | `import vnbroker` **không** nạp `.env`. Không có `dotenv` trong `vnbroker/`, `python-dotenv` chưa cài. Người dùng phải tự export biến. | Nạp `.env` ngầm là thay đổi hành vi có rủi ro bảo mật — cần quyết định của Owner, không tự ý làm trong một đợt sửa lỗi. Cổng `check_provider_consistency.py` tự nạp nên **gate vẫn kiểm được**. |
| **O2** | TCBS `intraday()` trả `"a": ""` cho **mọi** bản ghi (đo 2026-10-10, `/nyx/v1/intraday/TCB/his/paging`) ⇒ `match_type` toàn `unknown` trong khi KBS/VCI có `Buy`/`Sell`. | Đây là **server**, không phải mapping: `""` → `unknown` đúng là giá trị chuẩn hoá. Không được bịa dữ liệu. Đã ghi vào `CLAUDE.md`. |
| **O3** | `screener` của VCI và KBS trả **0 dòng** với các tham số thử được ⇒ chưa đối chiếu được `market_cap` bằng nguồn độc lập. | Đã có bằng chứng thay thế mạnh hơn: bất biến `market_cap` không đổi theo đơn vị giá (lệch 0.000000%) + đối chiếu số học tay với `listed_shares`. Ghi `CHƯA CHẠY` kèm lệnh. |

---

## 6. Phòng thủ cổng — bằng chứng cổng thật sự bắt lỗi

Một cổng chỉ được chạy trên input sạch thì **chưa** được kiểm. Đã inject lại 3 lỗi
mà bản gate cũ im lặng, rồi chạy lại:

| Lỗi được tiêm lại | Lệnh | Kết quả |
|:--|:--|:--|
| Bỏ phần nối provider vào cuối (F1) | `python scripts/check_provider_consistency.py` | **exit 1** — `C5 … pool phục vụ được ['dnse','tcbs'] … AUTO=['vci','kbs']` |
| Xoá mục `tcbs` khỏi `AUTH_PROVIDERS` (F3) | như trên | **exit 1** — `C4 … không có mục nào trong ProviderPool.AUTH_PROVIDERS` |
| Bỏ khoá `env_all` (F6) | như trên | **exit 1** — `C0 … thieu khoa cau hinh 'env_all'` |
| Cây nguyên bản | như trên | **exit 0** |
| `--self-test` | `python scripts/check_provider_consistency.py --self-test` | **exit 0**, 5 trường hợp âm đều `RED nhu mong doi` |

Mỗi lần tiêm đều khôi phục file bằng `write_text` từ bản trong bộ nhớ — **không**
dùng `git checkout --` (hazard 11).

---

## 7. Cổng chạy được nhưng bỏ sót (phát hiện ngoài phạm vi, để lại backlog)

| Nguồn phát hiện | Nội dung | Mức |
|:--|:--|:--|
| Audit Wave 1 | `logger.SENSITIVE_PATTERN` (`core/utils/logger.py:24-27`) yêu cầu dạng `key<sep>value`; token trần không có tên phía trước vẫn lọt. `str({"Authorization": f"Bearer {JWT}"})` cũng lọt vì lớp ký tự của regex dừng ở dấu cách. | minor, **có sẵn từ trước**, không do đợt này. Đáng làm vì đây là logger của lane tiền thật. |
| Audit Wave 1 | Bộ đọc `.env` của cổng không phải parser dotenv: không bóc dấu nháy, không xử lý tiền tố `export`. Đo: `.env` thật có 8 khoá, **không** khoá nào có nháy ⇒ vô hại hôm nay. | minor, backlog |
| Tác giả | PowerShell `Get-Content \| Measure-Object -Line` cho 1583 dòng với `common/data.py` trong khi `len(splitlines())` cho **1876**. Đếm bằng PowerShell làm tôi tưởng chỉ 5 file vượt 800L thay vì 11. | Đã ghi vào `docs/PLAN_TIER1_WAVE12_EXECUTION.md` §0 |

---

## 8. Phạm vi ngoài đợt này (những gì audit thấy nhưng không thuộc Wave 1+2)

- 11 file vượt ngân sách 800L (đo lại bằng Python, khớp con số `11` trong kế
  hoạch cha).
- `ruff-tests-all` KNOWN-RED 13 lỗi có sẵn.
- `mypy vnbroker` 1207 lỗi có sẵn; gate thật là `check_mypy_baseline.py`.
- Wave 3 (rate-limit thật) — vẫn giữ lý do hoãn của kế hoạch cha.

Không agent nào sửa những thứ này; ghi vào backlog để lát riêng.