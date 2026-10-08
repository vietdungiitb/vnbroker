# SUMMARY — agent-t2-bulk-fixes (4 MAJOR findings)

**Base commit của worktree: `8936f7d2`** (`dev` cục bộ — xem " Sai lệch về base" bên dưới).
**Trạng thái: KHÔNG merge, KHÔNG push.** 3 commit trên nhánh `feat/tier1-fix-bulk`.

| Commit | Nội dung |
|---|---|
| `35bfe4c` | MAJOR-1 + MAJOR-5 |
| `9e415dc` | MAJOR-2 |
| `085b885` | MAJOR-4 |

Tất cả 4 finding đã sửa. **Không có finding nào không sửa được.**

---

## Sai lệch về base — đã xử lý, cần coordinator biết

Lệnh được giao là `git worktree add ... -b feat/tier1-fix-bulk origin/dev`.
**`origin/dev` (`e5d8133`) đã cũ** — nó không chứa code mà audit chỉ tới:

| | `origin/dev` = `e5d8133` | `dev` cục bộ = `8936f7d` |
|---|---|---|
| `vnbroker/core/bulk_router.py` | 158 dòng, **không có** `call_provider_sync` | 384 dòng, có `call_provider_sync` tại `:256` |
| `tests/unit/api/test_bulk_api.py` | 101 dòng (audit trích `:317` → ngoài phạm vi) | 355 dòng (khớp `:231-245`, `:317`) |

`git log origin/dev..dev` = **21 commit chưa push**. Audit được thực hiện trên HEAD
cục bộ (`8936f7d`), khớp 100% số dòng mà báo cáo trích. Tôi đã xoá worktree cũ và
tạo lại từ `dev` cục bộ. Nếu ai đó merge nhánh này vào `origin/dev` thì họ cần
rebase lên `dev` cục bộ, không phải `origin/dev`.

---

## MAJOR-1 — health/circuit-breaker trên bulk path vô hiệu

### Trước (probe tự viết, `$env:TEMP`, chạy trên `8936f7d`)

```
call 6: failed=['KBS', 'VCI']
_health_state keys = ['quote/KBS', 'quote/VCI']
snapshot with any failure = {'VCI': (0, False), 'KBS': (0, False)}
healthy after 6 failed bulk calls = ['KBS', 'VCI']
```

Khớp đúng số đo của auditor. `get_source_health_snapshot`
(`core/source_router.py:332`) đọc `_health_state[(module, s)]` với `s` từ
`get_auto_candidates('quote')` = `['vci','kbs']` (lower-case), còn
`_select_providers` trả `[p.upper() ...]` ⇒ ghi khoá `('quote','VCI')` không ai đọc.

### Sau

```
call 1: failed=['KBS', 'VCI']
call 2: BLOCKED by circuit breaker -> No healthy providers available
_health_state keys = ['quote/kbs', 'quote/vci']
snapshot = {'VCI': {'failures': 1, 'in_cooldown': True}, 'KBS': {...}}
```

**Đã chọn (như yêu cầu, nêu rõ trong commit):** giữ `selected` **lower-case nội bộ**,
chỉ upper-case khoá trả về cho `api/bulk.py`, qua helper `_display_key` để có
đúng **một** điểm chuyển đổi. Không chọn phương án normalize trong
`record_failure`/`record_success` vì hai file đó ngoài claim.

> **Lưu ý kỹ thuật:** snippet khẳng định trong đề bài dùng `snapshot["vci"]` sẽ
> **ném `KeyError`** — `get_source_health_snapshot` trả khoá **UPPER-case**
> (`source_router.py:338`, `snapshot[source.upper()]`). Tôi dùng `snapshot["VCI"]`.
> Probe đầu tiên của tôi đã dính đúng lỗi này.

### Fail-before / pass-after

`pytest tests/unit/core/test_bulk_router.py tests/unit/api/test_bulk_api.py`
với source khôi phục từ `git show 8936f7d:...`:

| Trạng thái | Kết quả |
|---|---|
| baseline `8936f7d` | **6 failed**, 44 passed |
| sau fix | **50 passed** |

6 test đỏ tại baseline:
`test_bulk_failure_is_visible_in_health_snapshot` (`failures=0`) ·
`test_bulk_failure_uses_health_store_key_that_snapshot_reads`
(`['KBS','VCI']` không ai đọc) · `test_bulk_circuit_breaker_blocks_next_call_after_failure`
(`DID NOT RAISE`) · `test_ac4_all_providers_runtime_error_is_reported` (`failures=0`) ·
`test_ac4_all_providers_down_reports_failed` (`failures=0`) ·
`test_provider_failure_captured_not_crash` (mock so khớp `VCI` cũ).

---

## MAJOR-2 — tiêu chí "không dùng được" sai; `failed` nói dối mỗi ngày nghỉ

### Trước

```
A. frame DUNG COT + 0 DONG (ngay nghi):  errors={'VCI': "returned no data for 2 requested symbol(s)"}
B. frame 0 COT (provider hong):          errors={'VCI': "returned no data for 2 requested symbol(s)"}
```

**Hai trường hợp đối lập cho ra kết quả y hệt nhau** — đó là điểm nguy hiểm, không
chỉ là "báo lỗi sai".

### Sau

```
A. rows returned = {'VCI': 2}   errors={}          <- ngay nghi = THANH CONG
B. rows returned = {}           errors={'VCI': '...returned unusable data...'}
```

Đã **dùng lại** `_is_unusable_provider_result` của `common/data.py:442` qua bọc
wrapper `_is_unusable` (import trễ), thay vì viết lại — kèm test
`test_m2_bulk_reuses_the_data_module_schema_criterion` so 9 giá trị đầu vào giữa
hai đường đi. Thông điệp lỗi đổi `returned no data` → `returned unusable data`
vì "0 frame" nay nghĩa là "không frame nào có schema", không phải "0 dòng".

### Về vòng import (đề bài yêu cầu nói rõ nếu có)

**Không có vòng import** — đã kiểm chứng 3 cách:
1. `core.bulk_router` import trước, `common.data` sau → OK
2. `common.data` import trước, `core.bulk_router` sau → OK
3. Quét AST toàn cục từ `common.data`: `common.data -> core.bulk_router` edges = **NONE**

Vì vậy **không** cần dời helper ra `core/utils/*` (ngoài claim) và **không** cần
báo yêu cầu mở file unclaimed nào. Import trễ vì `common.data` là module nặng
(1873 dòng) và `core` nằm dưới nó.

### Fail-before / pass-after

`pytest tests/unit/core/test_bulk_router.py -k m2` (source từ `35bfe4c`):

| Trạng thái | Kết quả |
|---|---|
| trước fix `35bfe4c` | **5 failed**, 29 deselected |
| sau fix | **5 passed**, 29 deselected |

---

## MAJOR-4 — `core → api` inversion + bridge trùng lặp

### Trước

```
import tang cao trong core/bulk_router.py: ['vnbroker.api.quote (line 296)']
provider co parallel (VCI/KBS/TCBS) -> calls: [('history', (), '1D', False), ('history', (), '1D', False)]
```

Nghĩa là provider **có** năng lực song song mà bulk **không dùng** — cứ gọi tuần tự.

### Sau

```
import tang cao trong core/bulk_router.py: NONE
provider co parallel -> calls: [('history', ('ACB', 'VNM'), '1D', True)]   <- MOT lenh ca batch
provider KHONG co parallel -> calls: [('history-sequential','ACB'), ('history-sequential','VNM')]
```

Đã xác minh `history(parallel=True)` của VCI/KBS/TCBS tự route tới
`fetch_multiple` và tự giữ bridge (`explorer/vci/quote.py:496-516`), KBS/TCBS là
bản sync, VCI bọc `asyncio.run`. **Không sửa gì dưới `vnbroker/explorer/`.**

Phát hiện năng lực dựa trên **tên tham số tường minh**, không dựa trên `**kwargs`:
SSI/DNSE có `**kwargs`, gửi `symbols`/`parallel` vào sẽ bị nuốt im lặng — im lặng
là thứ tệ nhất, nên phải rơi về tuần tự.

### Không phải defect đã reproduce

`call_provider_sync` gọi `asyncio.run` mỗi lần trong khi `core/utils/async_client.py:246`
giữ singleton `AsyncClient`. Auditor đo `SAME OBJECT=True` và httpx không ném lỗi.
**Tôi không tái hiện được lỗi nào ở đây và không tuyên bố đã sửa.** Việc gỡ
`call_provider_sync` loại rủi ro, không phải sửa bug đã chứng minh.

### Fail-before / pass-after

`pytest tests/unit/core/test_bulk_router.py -k m4` (source từ `9e415dc`):

| Trạng thái | Kết quả |
|---|---|
| trước fix `9e415dc` | **6 failed**, 1 passed |
| sau fix | **7 passed** |

⚠ `test_m4_provider_without_parallel_falls_back_to_sequential` **PASS ở cả hai
bên** — nhánh tuần tự đã tồn tại trước đó. **Không dùng làm bằng chông cho fix**,
chỉ giữ để chặn thoái lui.

### Hệ quả phát hiện được: test pollution (đã sửa)

MAJOR-5 bắt buộc provider giả phải nằm ở slot AUTO thật (`vci`) để quan sát được
health snapshot — mà đó **chính là slot của provider thật**. `ProviderRegistry`
là singleton toàn cục nên `_DownProvider` sống tới hết phiên và làm
`tests/unit/api/test_quote_price_unit_consistency.py` chết bằng
`tenacity.RetryError`. **Chạy riêng file đó thì xanh — chỉ lộ dưới full-suite.**
Đã thêm save/restore `ProviderRegistry._registry` vào fixture autouse của cả hai
file test. (`_install_as_vci` trong `test_bulk_router.py` đã có sẵn nguy cơ này.)

---

## MAJOR-5 — AC-4 được "chứng minh" bằng call spy

Đã bỏ spy, chuyển sang khẳng định hậu quả trên
`source_router.get_source_health_snapshot("quote")`: `failures > 0` +
`in_cooldown is True`.

**Bằng chứng độc lập rằng spy là vô dụng** — tôi tự chạy lại test cũ trên baseline
`8936f7d` (source **và** test cùng khôi phục):

```
test_d3_empty_pool_raises_connection_error  PASSED
test_ac4_all_providers_down_reports_failed  PASSED   <- bản có spy
2 passed
```

Cả hai xanh ở commit gốc ⇒ không chứng minh được gì. Đúng như auditor nói.

### Provider giả phải nằm ở slot AUTO thật

Đề bài yêu cầu assert snapshot cho "provider đã fail", nhưng
`get_source_health_snapshot` chỉ liệt kê `get_auto_candidates('quote')` =
`['vci','kbs']`. Provider lạ như `downxx` **không bao giờ** xuất hiện trong đó —
"sức khoẻ của provider lạ" vốn không quan sát được. Nên test cài giả vào slot
`vci` thật. Đây là hệ quả bắt buộc của yêu cầu khẳng định hậu quả.

### `test_d3_empty_pool_raises_connection_error` — ĐÃ XOÁ

Đã tự xác minh: `ProviderPool.NO_AUTH_PROVIDERS = ["vci","kbs"]` là list hardcode
(`core/provider_pool.py:37`), nên `get_available_providers` **không bao giờ** rỗng
⇒ nhánh `raise ConnectionError("No providers available")` ở `api/bulk.py:72`
**không reachable**, và test cũ xanh ở commit gốc (xem bằng chứng trên).

Thay bằng `test_d3_pool_is_never_empty_so_empty_pool_branch_is_dead_code`, khẳng
định điều kiện thật. Test thay thế này **cũng PASS ở baseline** — nó ghi nhận sự
thật, **không** phải bằng chứng cho fix nào.

---

## Gates — exit code thật

| Gate | Lệnh | Kết quả | Exit |
|---|---|---|---|
| unit + contract | `pytest tests/unit tests/contract -q --timeout=300` | **1210 passed, 6 skipped** | **0** |
| toàn bộ test | `pytest tests/ -q --timeout=60` | **1255 passed, 30 skipped** | **0** |
| ruff | `ruff check vnbroker tests/unit tests/contract/` | `All checks passed!` | **0** |
| mypy baseline | `scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1209, fixed 57)` | **0** |

Baseline cùng lệnh trước khi sửa: **1194 passed, 6 skipped**, exit 0.
Hậu ngạch: **+16 test**, không mất test nào (46 → 62 trong 2 file của tôi).

`check_mypy_baseline.py` **không** chạy `--update`. Baseline vẫn ghi 1266 trong khi
số lỗi thực còn 1209 — tức đã có 57 lỗi được sửa so với baseline đang ghi; tôi để
nguyên theo yêu cầu.

> Dùng `--basetemp` riêng cho mọi lần chạy pytest: các agent song song dùng chung
> `$env:TEMP` sẽ tranh nhau `pytest-current` và gây
> `PermissionError: [WinError 5]` (đã gặp, không phải lỗi test).

## Test mới — 16 test, tất cả đều có fail-before

`tests/unit/core/test_bulk_router.py` (+12): 3 MAJOR-1, 5 MAJOR-2, 7 MAJOR-4,
cộng 2 test cũ được đổi khẳng định. `tests/unit/api/test_bulk_api.py` (+4/−2):
AC-4 viết lại, D3 xoá 1 thay 1, 2 test cũ đổi theo hình dạng gọi mới.

Không xoá test nào mà không nói lý do. `test_ac1_async_fetch_multiple_is_awaited`
được **đổi tên + đổi hình dạng fake** thành
`test_ac1_async_provider_underneath_still_yields_rows`: fake giờ mô phỏng đúng
VCI (`history` sync → `fetch_multiple` async qua `asyncio.run`) để giữ nguyên ý
cũ (lớp `core` không còn cần tự quản lý event loop) thay vì xoá.

## File unclaimed mà tôi cho là **KHÔNG** cần sửa

Đã kiểm tra từng file trong danh sách non-goal và **không cần đụng tới**:
`vnbroker/explorer/**` (năng lực đã có, chỉ gọi vào) · `vnbroker/common/data.py`
(helper được **dùng lại**, không sửa) · `vnbroker/core/source_router.py` và
`vnbroker/core/health_router.py` (sửa được từ phía `bulk_router`) ·
`vnbroker/core/utils/**` (không cần dời helper vì không có vòng import) ·
`vnbroker/api/quote.py` (`call_provider_sync` còn nguyên cho chỗ khác dùng; chỉ
bulk không dùng nữa).

## Rủi ro còn lại

1. **Provider ngoài AUTO candidates vẫn không quan sát được health.** Bulk có thể
   chạy provider tên lạ (pool tương lai, provider thứ ba) nhưng snapshot chỉ liệt
   kê `vci/kbs` ⇒ `record_failure` ghi khoá không ai đọc. Sửa được thật sự phải ở
   `source_router.get_source_health_snapshot` (ngoài claim). **Đây là hạn chế còn
   tồn tại sau MAJOR-1, không phải đã giải quyết trọn vẹn.**
2. **Hai lớp abstraction giống nhau:** `_is_unusable` + `_is_usable_frame`, trong đó
   `_is_unusable` gọi `common.data` **trong** vòng lặp. Rẻ hơn import, nhưng nếu
   `common.data` được import muộn thì vẫn phải trả giá import một lần.
3. **Tỉ lệ lỗi đổi thông điệp** ("no data" → "unusable data"): có thể làm hỏng test
   hoặc log-alert nào đang khớp chuỗi cũ. Tôi đã quét trong 2 file của mình;
   **chưa quét toàn repo** (ngoài claim).
4. **Đường song song giờ phụ thuộc `history` hơn là `fetch_multiple`.** Với provider
   tương lai có `fetch_multiple` nhưng `history` **không** có `parallel`, bulk sẽ rơi
   về tuần tự và **mất** throughput song song. Trước đây nó gọi `fetch_multiple`
   thẳng. Đây là đánh đổi có chủ ý (bỏ bridge trùng lặp), nhưng cần biết.
5. **Test pollution là mối hiểm của registry singleton.** Đã khoá bằng fixture ở 2
   file của tôi, nhưng **bất kỳ test nào khác** cài giả vào slot `vci`/`kbs` mà
   không khôi phục đều có thể làm hỏng test chạy sau theo thứ tự. Đây là vấn đề
   thiết kế của registry, không thuộc claim.
6. **`tests/unit/api/test_quote_price_unit_consistency.py` là bẫy thứ tự.** Rỗng
   khi chạy riêng, đỏ khi chạy cả thư mục — đã gặp và đã sửa gốc, nhưng bất kỳ ai
   thêm test giả vào registry cũng sẽ dính lại.