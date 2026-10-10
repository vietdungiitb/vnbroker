# SUMMARY — agent `t2-cache-fixes` — MAJOR-3 (cache-key encoder)

**Claim duy nhất:** `vnbroker/core/utils/cache.py` + `tests/unit/core/test_cache_key.py`
**Worktree:** `C:\Users\PHAMVI~1\AppData\Local\Temp\opencode\t1-fixes-cache`
**Branch:** `feat/tier1-fix-cache`
**HEAD trước khi sửa:** `8936f7d25df7ad3ff8edbbff8746b9b2a206ff11` (`merge(slice1): bulk thuc su lay duoc du lieu`)

> **LƯU Ý VỀ BASE — đã phải chệch khỏi chỉ dẫn, ghi lại để coordinator biết.**
> Chỉ dẫn bảo `git worktree add … origin/dev`. `origin/dev` tại thời điểm này là
> `e5d8133` — **cũ hơn `dev`**, và **không chứa dòng code bị audit**: ở `origin/dev`
> `cache.py` còn là bản cũ với `key_parts = [str(arg) for arg in args if isinstance(arg, (str,int,float,bool,type(None)))]`,
> **không** có `PRIMITIVES`, `_encode_value`, cũng không có docstring dòng 29. Số dòng audit trích
> (29 / 37 / 56) khớp **chính xác** với `dev` = `8936f7d`. Vì `origin/dev` là **tổ tiên** của `dev`
> (`git merge-base --is-ancestor origin/dev dev` → 0), tôi đã `git reset --hard dev` để lấy đúng
> code bị audit. Nếu tôi sửa trên `origin/dev` thì tôi đang sửa **một bug khác** (bản đó âm thầm
> **loại bỏ** mọi arg không phải primitive thay vì làm va chạm key) — sai mục tiêu.

---

## 1. Mức độ nghiêm trọng — nói đúng, không thổi phồng

Đây là **sai hợp đồng + bẫy đã vũ trang, KHÔNG phải sự cố đang xảy ra.**

Auditor đã kiểm tra cả 12 hàm `@cached_listing`/`@cached_industry` thật trong repo
(`explorer/kbs/listing.py`, `vci/listing.py`, `dnse/listing.py`, `tcbs/listing.py`,
`ssi/listing.py`, `ssi/indices.py`, `ssi/securities.py`, `ssi/trading.py`) và chúng **chỉ nhận
`str`/`bool`/`Optional[str]`** — không hàm nào nhận DataFrame hay object bất kỳ. Với `str`,
`bool`, `Optional[str]` thì `str(value)` là **đã đủ phân biệt**. ⇒ **Không caller nào hiện hữu bị
hại.** Không có dữ liệu nào bị trả nhầm trong điều kiện vận hành hiện tại.

Cái thực sự sai: docstring tuyên bố một bất biến mà code **không** bảo đảm, nên bất kỳ ai đọc
docstring rồi viết hàm cache mới với tham số `date` hay `list` (đã xảy ra ở VN-2, đã sửa) sẽ tin
tưởng nhầm. Đây là bẫy, không phải tai nạn.

---

## 2. Reproduce trước khi sửa (probe của tôi, không dùng lại số của auditor)

`$env:TEMP\probe_cache_key.py`, chạy với `PYTHONPATH` trỏ worktree. **7 vấn đề.**

| pair | key tại `8936f7d` | kết luận |
|---|---|---|
| `None` vs `"None"` | `f\|None` vs `f\|None` | **VA CHẠM** |
| `0` vs `"0"` | `f\|0` vs `f\|0` | **VA CHẠM** |
| `1` vs `"1"` | `f\|1` vs `f\|1` | **VA CHẠM** |
| `1` vs `True` | `f\|1` vs `f\|True` | khác *(xem ghi chú)* |
| `1` vs `1.0` | `f\|1` vs `f\|1.0` | khác *(xem ghi chú)* |
| `DataFrame({"a":[1,2,3]})` vs `([9,9,9])` | `f\|DataFrame` vs `f\|DataFrame` | **VA CHẠM** |
| `Decimal('1')` vs `Decimal('2')` | `f\|Decimal` vs `f\|Decimal` | **VA CHẠM** |
| `Obj('a')` vs `Obj('b')` | `f\|_Configured` vs `f\|_Configured` | **VA CHẠM** |
| `{"a":1}` vs `{"a":2}` (control) | `f\|dict:1:{a=1}` vs `f\|dict:1:{a=2}` | ok |
| `date` 2024 vs 2026 (control) | `f\|date:2024-01-01` vs `…2026-10-08` | ok |
| `["ACB","VNM"]` vs `["VNM","ACB"]` (control) | khác | ok |

**Ghi chú trung thực về `1`/`True`/`1.0`:** 3 dòng này **KHÔNG va chạm** tại `8936f7d`, vì
`str(True)=='True'` và `str(1.0)=='1.0'` tình cờ khác `str(1)=='1'`. Auditor liệt kê chúng như
cần chống; tôi **giữ nguyên** hành vi này và làm nó **cấu trúc** thay vì tình cờ — có nhãn kiểu
thì `1`/`True`/`1.0` không thể trùng bất kể `str()` ra gì.

### 2.1 Reproduce rò rỉ payload (damage thật)

```
set under key(df1)='f|DataFrame'
get under key(df2)='f|DataFrame'
-> 'PAYLOAD_FOR_DF1'
LEAK | cache[df2-key] returned the df1 payload
```

Sau khi sửa:

```
set under key(df1)='p5:str:f|p40:obj:pandas.DataFrame|   a\n0  1\n1  2\n2  3'
get under key(df2)='p5:str:f|p40:obj:pandas.DataFrame|   a\n0  9\n1  9\n2  9'
-> None
```

### 2.2 Hai lỗi nhỏ auditor nêu — **ĐÃ SỬA CẢ HAI**

**dict insertion order.** `{1:'x','1':'y'}` → `f|dict:2:{1=x,1=y}`; `{'1':'y',1:'x'}` → `f|dict:2:{1=y,1=x}`.
Nguyên nhân: sort **sau** khi encode, mà `str(1)` và `str('1')` cùng ra `'1'` nên sort ổn định giữ
nguyên thứ tự chèn. Nay sửa bằng cách sort **cặp đã encode** (`sorted((enc(k), enc(v)))`) — độc lập
thứ tự chèn ngay cả khi hai token trùng nhau. Sau: cả hai → `p5:str:f|p32:dict:2:{int:1=str:x,str:1=str:y}`.

**Separator `|`/`=`.** `_make_key("x", 1)` = `'x|1'` vs `_make_key(x=1)` = `'x=1'` — trước đây chỉ
khác nhau **tình cờ** vì không tham số nào chứa `=`. Đã làm chắc: mỗi trường giờ có **tiền tố độ dài**
(`p<len>:<token>` / `k<len(name)>:<name>=<len>:<token>`), nên ranh giới trường là **cấu trúc**, không
còn là may mắn. Probe đối kháng 20 ca — tất cả key khác nhau:

```
K("x|1")        = 'p7:str:x|1'
K("x", 1)       = 'p5:str:x|p5:int:1'          <- khác, trước là trùng
K("x=1")        = 'p7:str:x=1'
K(x=1)          = 'k1:x=5:int:1'
K("k1:x=5:int:1")= 'p16:str:k1:x=5:int:1'       <- không giả lập được kwarg thật
K(x=1, "…")     = 'p16:str:k1:x=5:int:1|k1:x=5:int:1'
```

---

## 3. Sửa gì

### 3.1 Nhánh primitive — nhãn kiểu

`if isinstance(value, PRIMITIVES): return str(value)` → các nhánh riêng có nhãn:
`none` · `str:` · `int:` · `float:{value!r}` · `bool:`. Thứ tự kiểm tra bắt buộc vì `bool` là
subclass của `int`.

### 3.2 Nhánh object — bỏ `type(v).__name__`

`_encode_object()` dựng token từ: tên đầy đủ `module.Qualname` + `repr()` đã **che address** +
**state của instance** (`__dict__`, hoặc `__slots__`) *khi state đó an toàn để đọc*
(`_is_terminal`). Nhờ vậy `Decimal('1')`≠`Decimal('2')`, 2 DataFrame khác nhau khác nhau,
`Obj('a')`≠`Obj('b')` — còn 2 instance **cùng state** vẫn ra cùng token ⇒ cache vẫn hit.

**Bẫy tôi phát hiện khi làm theo gợi ý của task:** `re.sub(r"0x[0-9a-f]+", "0x?", repr(v))` **không
che nổi address viết HOA** mà CPython thực sự in ra:
`0x000001E65D248D70` → `0x?E65D248D70` (regex dừng ở chữ `E`). Mọi object sẽ vẫn trông khác nhau ⇒
cache **không bao giờ hit**. Regex đã dùng: `0[xX][0-9a-fA-F]+`, thay bằng `<addr>` (không phải
`0x?` — để không còn chữ `0x` nào trong key, đúng như hợp đồng "address-free"). Có test riêng
(`test_uppercase_hex_addresses_are_masked_too`).

### 3.3 Bảo đảm tính quyết định (deterministic)

- Mọi `repr()` đều đi qua `_ADDR_MASK` ⇒ không address nào tham gia key.
- Token quá dài (>4096 ký tự) được thay bằng **BLAKE2b-128**, **không** dùng `hash()` vì
  `hash(str)` bị salt theo `PYTHONHASHSEED`.
- **Đo thật:** cùng một key phức tạp chạy ở `PYTHONHASHSEED` = `0`, `1`, `12345` → **3 tiến trình
  riêng, 1 key giống hệt nhau**.

### 3.4 Sửa docstring

Docstring cũ *"Every branch keeps the value's information, so different arguments cannot share a
token"* đã bị thay bằng bất biến **thực sự** đã cài: *"hai tham số chỉ chung token khi chúng không
phân biệt được"* + *"mọi tham số bằng nhau luôn chung token"* + **giới hạn tồn đọng** (xem §6).

### 3.5 Hai cải tiến phát sinh (đều có test)

- **Container tự tham chiếu không còn `RecursionError`** (`_MAX_DEPTH = 6`). Trước đây `x=[]; x.append(x)`
  làm vỡ stack **ngay khi dựng key** — đã xác nhận FAIL trước, PASS sau.
- **`__repr__` ném exception không còn làm hỏng cache** (`try/except` trong `_encode_object`).

### 3.6 KHÔNG đụng vào TTL / eviction / thread-safety

Chỉ suy ra key. `get`/`set`/`delete`/`clear`/`_evict_if_needed`/`cleanup_expired`/`stats` và toàn bộ
`cached_listing`/`cached_industry` giữ nguyên logic.

---

## 4. Fail-before / pass-after — bằng chứng từng test

Cách làm đúng yêu cầu, **không dùng `git checkout -- <file>`** (sẽ xoá code chưa commit):

```powershell
Copy-Item vnbroker\core\utils\cache.py $env:TEMP\cache_FIXED_t2.py -Force
git show 8936f7d25df7ad3ff8edbbff8746b9b2a206ff11:vnbroker/core/utils/cache.py > vnbroker/core/utils/cache.py
# → chạy test, ghi FAIL
Copy-Item $env:TEMP\cache_FIXED_t2.py vnbroker/core/utils/cache.py -Force
# → chạy lại, ghi PASS
```

SHA256 để đối chiếu: pre-fix `083E3ECC…795` · bản của tôi `7E15219D…C5` · sau khi restore khớp
`7E15219D…C5` ⇒ **không mất code nào**.

**Trước fix:** `20 failed, 32 passed`, exit `1`
**Sau fix:** `52 passed`, exit `0`

### 4.1 20 test MỚI FAIL trước fix → PASS sau fix

| # | test | thông báo lỗi trước fix |
|---|---|---|
| 1 | `test_none_and_the_string_none_do_not_collide` | `assert 'f\|None' != 'f\|None'` |
| 2 | `test_int_and_the_matching_string_do_not_collide[0]` | `assert 'f\|0' != 'f\|0'` |
| 3 | `test_int_and_the_matching_string_do_not_collide[1]` | `assert 'f\|1' != 'f\|1'` |
| 4 | `test_primitive_type_labels_survive_in_the_key` | `assert 'none' in 'f\|None\|True\|1\|1.0'` |
| 5 | `test_dataframes_with_different_contents_do_not_collide` | `assert 'f\|DataFrame' != 'f\|DataFrame'` |
| 6 | `test_decimals_with_different_values_do_not_collide` | `assert 'f\|Decimal' != 'f\|Decimal'` |
| 7 | `test_objects_with_different_state_do_not_collide` | `assert 'f\|_Configured' != 'f\|_Configured'` |
| 8 | `test_slotted_objects_with_different_state_do_not_collide` | `assert 'f\|_Slotted' != 'f\|_Slotted'` |
| 9 | `test_object_keys_carry_no_address_at_all` | `assert '<addr>' in 'f\|_FakeObj'` |
| 10 | `test_cache_does_not_serve_another_dataframes_payload` | `assert 'PAYLOAD_FOR_LEFT' is None` |
| 11 | `test_cache_does_not_serve_another_objects_payload` | `assert 'PAYLOAD_A' is None` |
| 12 | `test_cache_does_not_serve_another_decimals_payload` | `assert 'PAYLOAD_1' is None` |
| 13 | `test_cache_round_trip_for_every_collision_pair` | `AssertionError: (None, 'None')` |
| 14 | `test_dict_insertion_order_does_not_change_the_key` | `assert 'f\|dict:2:{1=x,1=y}' == 'f\|dict:2:{1=y,1=x}'` |
| 15 | `test_lookalike_dict_keys_both_survive_the_sort` | `assert 'f\|dict:1:{1=x}' != 'f\|dict:1:{1=x}'` |
| 16 | `test_separator_characters_inside_a_value_cannot_forge_a_field` | `assert 'x\|1' != 'x\|1'` |
| 17 | `test_one_argument_containing_a_separator_is_not_two_arguments` | `assert 'x\|1' != 'x\|1'` |
| 18 | `test_self_referential_container_does_not_break_key_generation` | `RecursionError: maximum recursion depth exceeded` |
| 19 | `test_oversized_object_token_is_digested_not_truncated_away` | `assert 'blake2b128' in 'f\|Long'` |
| 20 | `test_object_repr_is_the_ceiling_on_discrimination` | `assert 'f\|DataFrame' != 'f\|DataFrame'` |

### 4.2 7 test MỚI PASS cả trước lẫn sau — **không phải** test fail-before

Nói thẳng để không tính nhầm công lao:

| test | vì sao pass trước fix |
|---|---|
| `test_values_that_compare_equal_still_get_different_keys` | `1`/`True`/`1.0` đã khác nhau **tình cờ**; nay khác **cấu trúc** |
| `test_positional_and_keyword_arguments_are_separated` | `'x\|1'` vs `'x=1'` đã khác; nó **không** chứng minh điều gì — các test #16/#17 mới là cái chứng minh "may mắn" ấy **không** giữ được |
| `test_dataframes_with_equal_contents_still_share_a_key` | control tích cực (cache phải hit) |
| `test_objects_with_equal_state_still_share_a_key` | control tích cực — chính là bẫy của bản che-repr-mộc |
| `test_uppercase_hex_addresses_are_masked_too` | **guard cho code MỚI**: trước fix không có `repr()` nào để che |
| `test_key_generation_survives_a_broken_repr` | guard cho `try/except` mới |
| `test_no_key_contains_a_memory_address_for_any_argument_shape` | catch-all; trước fix vốn đã sạch |

### 4.3 2 test CŨ đã viết lại (pass trước và sau)

Hai test này **vỡ** khi tôi đổi định dạng key — chúng khẳng định **chuỗi literal của format cũ**, không
phải hành vi. Đã viết lại để khẳng định bất biến thật:

| test | khẳng định cũ (vỡ) | khẳng định mới |
|---|---|---|
| `test_cache_key_no_object_id` | `"object at" not in key` | 2 instance khác nhau ⇒ **cùng** key (chỉ đúng khi address không tham gia) + không có `0x` |
| `test_cache_key_filters_non_primitive_kwargs` | `"good=ok" in key` | round-trip `set`/`get`: khác `good` ⇒ miss, giống `good` ⇒ hit |

Cả hai **pass trước fix và sau fix** — chúng là test định dạng-độc-lập, không phải fail-before.

### 4.4 Round trip thật (không chỉ so key)

`test_cache_round_trip_for_every_collision_pair` chạy đủ 8 pair của bảng audit: với mỗi pair
`(left, right)` → `set(key(left), P)` rồi `get(key(right))` phải là `None` **và**
`get(key(left))` phải trả `P`. Đây là bằng chứng damage thật, không phải so chuỗi key.

Các case "vẫn phải hit" (cache không được bao giờ miss): `date` giống nhau · `list` giống nhau ·
dict cùng nội dung khác thứ tự chèn · 2 object cùng state · 2 DataFrame cùng nội dung ·
2 object slotted cùng state — **đều PASS**, và `test_cache_still_hits_for_repeated_non_primitive_arguments`
(khẳng định đếm số lần gọi hàm) vẫn xanh.

---

## 5. Gates — exit code THẬT

| gate | lệnh | kết quả | exit |
|---|---|---|---|
| unit + contract | `pytest tests/unit tests/contract -q --timeout=300` | **1221 passed, 6 skipped** (baseline `1194` + 27 test mới) | **0** |
| full suite | `pytest tests/ -q --timeout=60` | **1266 passed, 30 skipped** | **0** |
| ruff | `ruff check vnbroker tests/unit tests/contract/` | `All checks passed!` | **0** |
| mypy baseline | `python scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1209, fixed 57)` | **0** |

Không chạy `--update` cho mypy. Baseline 1194 chạy **trước** khi sửa cũng ra `1194 passed, 6 skipped`,
exit `0` — không hồi quy.

> Vệt `PermissionError … pytest-current` cuối output là artifact của pytest-tmpdir trên Windows,
> xuất hiện **giống hệt** ở lần chạy baseline, và **không** ảnh hưởng exit code (0).

**CI của repo này tắt (`duration_ms: 0`) — mọi gate trên đều chạy local.**

---

## 6. CHƯA CHẠY / giới hạn tồn đọng — ghi rõ, không giấu

1. **Không có integration test nào chạm `cache.py`.** Kiểm chứng chỉ ở mức unit + contract +
   probe. Không có bằng chứng runtime nào ngoài process (ví dụ nhiều process dùng chung cache —
   cache này là **in-memory**, nên vốn đã không chia sẻ giữa process).
2. **Giới hạn tồn đọng thật: chính `__repr__` của object là trần.** pandas cắt frame sau
   `display.max_rows`, nên 2 frame chỉ khác nhau ở dòng **bị che** sẽ **cùng token**. Tôi **đã ghim
   cái này thành test** (`test_object_repr_is_the_ceiling_on_discrimination`) để giới hạn **nhìn
   thấy được** trong test suite thay vì chỉ nằm trong docstring. **KHÔNG sửa** — sửa sẽ phải
   special-case pandas trong một cache generic (kéo pandas vào hot path). Không caller nào đẩy
   DataFrame qua `_make_key`, nên đây là **ràng buộc của hợp đồng**, không phải bug đang sống.
   *Cần đổi nếu* sau này có hàm cache DataFrame.
3. **Object không có state quan sát được vẫn không phân biệt được.** Ví dụ `class S: __slots__ = ()`.
   Hai instance đó **phải** cùng key — nếu khác thì cache **không bao giờ hit**, phá vỡ yêu cầu
   "identical args still collide". Không thể vừa cấm address vừa phân biệt được chúng. Đây là
   **giới hạn cơ bản** của bất biến đã chọn, đã ghi trong docstring.
4. **`_encode_value` là hàm private** (`_` tiền tố) nhưng `test_cache_key_filters_non_primitive_kwargs`
   cũ đã gọi nó qua hành vi. API công khai (`__all__`) **không đổi**.
5. **Chưa đo `hit_rate` production.** Sau PR nên xem log `Cache HIT/MISS` ở `debug` vài ngày để
   chắc việc thêm nhãn kiểu **không làm giảm** tỉ lệ hit ở workload thật (về lý thuyết không: với
   `str`/`bool`/`Optional[str]` — thứ mà cả 12 hàm thật nhận — token vẫn 1-1 với giá trị).
6. **`invalidate_*(pattern=...)` dùng substring match.** Định dạng key có tiền tố độ dài nên một
   `pattern` cắt ngang ranh giới trường sẽ không khớp. **Không có caller nào trong repo truyền
   `pattern`** (đã grep: chỉ có 2 định nghĩa `invalidate_listing_cache` / `invalidate_industry_cache`,
   0 call site có tham số) ⇒ không hỏng gì hôm nay, nhưng là **hợp đồng tiềm ẩn**.

---

## 7. Rủi ro

| rủi ro | mức | xử lý |
|---|---|---|
| Định dạng key đổi ⇒ cache cũ trong RAM không đọc lại được | **thấp** | cache là **in-memory**, không sống sót restart ⇒ không có tương thích dữ liệu nào cần giữ |
| `blake2b` + `repr` làm key dài hơn trước | **rất thấp** | key chỉ là dict key của string; có cap 4096 + digest |
| Đọc `__dict__` của object lạ có thể chậm/ném lỗi | **thấp** | chỉ đọc khi mọi value đều "terminal" (`_is_terminal`), và `getattr(..., None)` + `try/except repr` |
| Object giữ `__dict__` chứa thứ **không** terminal (vd bound method, session) ⇒ bỏ qua state, chỉ còn dựa vào `repr` | **trung bình** | an toàn theo hướng *bỏ qua* chứ không *ném lỗi*; đã ghi trong docstring `_instance_state` |
| Sửa 2 file đã claim, không đụng file khác | — | `git status` chỉ có 2 file |

---

## 8. File đã đổi

| file | +/− | nội dung |
|---|---|---|
| `vnbroker/core/utils/cache.py` | +191/−27 | `_encode_value` có nhãn kiểu; `_encode_object` + `_instance_state` + `_is_terminal`; `_ADDR_MASK` **hoa/thường**; `_MAX_DEPTH`; digest BLAKE2b; `_make_key` có tiền tố độ dài; docstring nói đúng bất biến thật |
| `tests/unit/core/test_cache_key.py` | +344/−2 | **+27 test mới** (6 nhóm), 2 test cũ viết lại cho định dạng-độc-lập |

Không đụng `bulk_router.py`, `api/bulk.py`, `common/data.py`, `docs/CLAIMS.md`, `CHANGELOG.md`.
TTL / eviction / thread-safety **không đổi**.
**CHƯA merge. CHƯA push.**

### Phát hiện phụ nên báo coordinator (không tự sửa — ngoài claim)

- `docs/SUMMARY_agent-t1-netpool.md:37` và `docs/REPORT_FIX_FINAL.md:25` mô tả bản sửa VN-2 cũ là
  *"`_make_key` dùng `str(arg)` cho mọi arg → key chứa memory address"*. Mô tả đó **không còn đúng**
  sau `8936f7d` (đã có `PRIMITIVES` + `_encode_value`). Tài liệu lệch với code — thuộc `docs/`,
  không phải claim của tôi.