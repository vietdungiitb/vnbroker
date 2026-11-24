# Plan: CafeF reference layer + route `adjusted=False` sang CafeF

**Ngày:** 2026-11-24  
**Branch hiện tại:** `feat/kbs-vci-adjusted-param` → đổi `feat/cafef-reference` (+ đổi tên claim)  
**Base:** `e996cb4` + slice `adjusted` đã code (chưa merge)  
**Lessons áp dụng: [L-P03, L-P06, L-E01, L-E06, L-P04]**

## 1. Quyết định Owner (2026-11-24) — đã chốt

1. **XLSX primary + JSON fallback** (số liệu §2).
2. **Facade `Vnbroker.reference("cafef")`**.
3. **KBS/VCI `adjusted=False` → route sang CafeF**, không còn fail-only.

CafeF là **reference/cross-check layer**, KHÔNG đăng ký vào `ProviderRegistry`,
`SUPPORTED_SOURCES`, `OPEN_SOURCE_CANDIDATES` hay AUTO pool. Thiết kế:
`docs/evidence/CAFEF_REFERENCE_LAYER_DESIGN_20261124.md`.

## 2. Bằng chứng chọn XLSX (đo thật)

| Ca | XLSX | JSON |
|---|---|---|
| 1 mã / 1 năm (TPB 2022) | 1,22 s download + 0,16 s parse = **1,4 s**, 1 request | 10 request × 1,44 s = **14,4 s** |
| All HOSE / 1 năm | 4,47 MB, 2,37 s + 34–40 s parse, 101.756 dòng, 0 duplicate, 0 date-fail | ~3.400 request ≈ **82 phút** |
| 5 ngày / 1 mã | ~1,3 s | 1,33 s (ngang) |

## 3. Kiến trúc & file chạm

### 3.1 Module mới
```
vnbroker/reference/{__init__,const,client,parser,reconcile,cafef}.py
```
`CafefReference.history(symbol, start, end, exchange=None)` → reference frame (schema §4);
`CafefReference.reconcile(frame, ...)` → báo cáo tỷ lệ/rebase/double-adjust.

### 3.2 Facade
`vnbroker/common/client.py`: `Vnbroker.reference(name="cafef")` — lazy import, validate tên.
**Không sửa** `vnbroker/__init__.py` (đang bị claim stale F-01 ở `CLAIMS.md:281`) — lazy proxy
`__init__.py:32-34` trả instance class thật nên method mới tự thấy.

### 3.3 Route `adjusted=False` — chốt vị trí (O-1, O-6)

**KBS `history()`** (`kbs/quote.py:341`):
1. Nhánh `parallel or symbols`: gọi `fetch_multiple(..., adjusted=adjusted)` rồi return (giữ nguyên).
2. Resolve `start/end` (đoạn `:358-399`) — helper **phải đặt SAU đây**.
3. Nếu `adjusted is False`: gọi `_cafef_raw_records(symbol, start, end, interval)` trả **records dạng
   native của KBS** (`t,o,h,l,c,v`, với `t` là chuỗi `YYYY-MM-DD HH:MM`). **Nhảy thẳng** tới
   `df = pd.DataFrame(records)` (`kbs:482`) — bỏ qua `send_request` (`:446`), kiểm tra `data_key`
   (`:465-469`) và nhánh `to_df=False` (`:478-479`). Sau đó fall through qua
   `rename/to_datetime/sort/astype/normalize/trim/attrs` hiện có (`:486-517`).
   Với `to_df=False` + `adjusted=False`: trả `json.dumps(records)` ngay (không normalize) —
   khớp ngữ nghĩa `to_df=False` hiện tại.
4. Nếu interval ≠ `1D` → `ProviderBadRequestError` rõ ràng (L-P06).
5. **Xoá hoàn toàn 4 guard `_require_raw_price_support` cũ** tại `kbs:197`, `kbs:366`,
   `vci:391`, `vci:531` (O-10) — nếu còn, AC-7/`fetch_multiple` sẽ ném ngay.

**VCI `history()`** (`vci/quote.py:531`):
1. Nhánh parallel → `fetch_multiple(..., adjusted=adjusted)` (đã có từ slice trước).
2. Resolve dates (`_resolve_dates`).
3. `adjusted is False` → helper trả **records dạng native của VCI** (`t,o,h,l,c,v`, với `t` là
   **epoch giây int**) để `ohlc_to_df` chạy đúng `transform.py:373-376` (`astype(int)`) —
   **KHÔNG dùng ISO string** (O-1). Fall through qua `ohlc_to_df` hiện có.
4. `history_async()` tương tự (helper sync, gọi trực tiếp — ghi rõ blocking).

**Metadata (O-2):** sau khi tail chạy, ghi đè `df.attrs['source']='cafef'`,
`df.attrs['data_origin']='cafef'`, và với VCI cả `df.source='cafef'` (`transform.py:413` gán `VCI`).
`data_origin` là marker riêng, **không bị** `annotate_result_source` (`source_router.py:517`) ghi đè.

**fetch_multiple:** mỗi symbol tự route qua `history/history_async(adjusted=...)` — không cần helper riêng.

## 4. Schema reference frame (khác tier-1)

`time, open, high, low, close(=raw), close_raw, close_adjusted, volume, value,
put_through_volume, put_through_value, source='cafef', fetched_at`
tz-aware `Asia/Ho_Chi_Minh`; giá ×1000; value ×1e9; request `MM/DD/YYYY`, response `%d/%m/%Y`.

## 5. AC (Given/When/Then) — đã đóng O-2/O-3/O-7/O-8

| ID | Given | When | Then |
|---|---|---|---|
| AC-1 | `Vnbroker().reference("cafef")` | gọi | trả `CafefReference`; tên khác → `ValueError` |
| AC-2 | golden TPB 04/01/2022 | `CafefReference.history(...)` | `close_raw=42750`, `close_adjusted=17940`, `vol=11034900`, `value=467.26e9`, tz đúng |
| AC-3 | XLSX mock fail | `history(...)` | fallback JSON pagination, vẫn ra frame đúng |
| AC-4 | date `31/12/2022` | `history(...)` | reject/swap đúng, không trả nến 2021 |
| AC-5 | KBS explorer, **mock `CafefReference.history`** (seam import trễ), patch `send_request` | `history("TPB", 2022-01-01..01-06, adjusted=False)` | trả 6 cột, `close=42750`; assert CafeF mock **được gọi**, `send_request` **không** |
| AC-5b | cùng AC-5 | assert attrs | `attrs['source']=='cafef'`, `attrs['data_origin']=='cafef'` (VCI: cả `df.source=='cafef'`) |
| AC-6 | VCI `history_async(adjusted=False)`, mock CafeF | await | `time` là epoch-int đầu vào, ra `close=42750`, attrs đúng |
| AC-7 | **Explorer** `fetch_multiple(adjusted=False, symbols=[...])` (api không có param này) | gọi | mỗi symbol gọi CafeF |
| AC-8 | `interval="1H", adjusted=False` | gọi | `ProviderBadRequestError`, message "chỉ daily" |
| AC-9 | `reconcile(kbs_frame, ...)` | gọi | ratio ~0,935 ± tolerance; flag rebase; **không mutate** frame đầu vào |
| AC-10 | `api.quote.Quote(source="KBS").history(adjusted=False)`, mock CafeF | gọi | `close=42750`, không `RetryError` (không dùng fake ném sẵn lỗi) |
| AC-11 | import xong | `get_auto_candidates("quote")` + `ProviderRegistry` | không có `cafef`; AUTO + `adjusted=False` → `attrs['data_origin']=='cafef'` |
| AC-12 | `adjusted=False, to_df=False` | gọi `history` | trả JSON string của raw records; **không** gọi `send_request`, không normalize |

## 6. Regression — liệt kê cụ thể (O-5)

**8 test cần viết lại (7 sẽ ĐỎ + 1 xanh-proxy vô nghĩa):** `tests/unit/explorer/test_quote_adjusted_parameter.py`
- `:41` `test_history_adjusted_false_raises_clear_error[kbs]`
- `:41` same `[vci]`
- `:107` `test_fetch_multiple_adjusted_false_raises_before_network[kbs]` / `[vci]`
- `:121` `test_parallel_history_adjusted_false_raises_before_fetch_multiple[kbs]` / `[vci]`
- `:136` `test_vci_history_async_adjusted_false_raises`
- `:147` `test_api_quote_history_adjusted_false_is_not_retry_error` (xanh nhưng đã proxy)

**7 test giữ nguyên:** default behaviour `[kbs]/[vci]`, explicit-None `[kbs]/[vci]`,
api network-retry, `test_raw_price_error_is_not_failover`, `test_not_implemented_error_would_have_been_failover`.

Cập nhật docstring `api/quote.py:158-161` (còn nói False → ProviderBadRequestError).

## 7. Slice & TDD

| Slice | Nội dung | Test |
|---|---|---|
| R1 | `reference/{const,client,parser,__init__}.py` (XLSX+fallback) | AC-2/3/4 |
| R2 | `reconcile.py` | AC-9 |
| R3 | Facade `Vnbroker.reference` | AC-1 |
| R4 | Route KBS/VCI (đúng vị trí O-6, metadata O-2) + **viết lại 8 test** | AC-5/5b/6/7/8/10 |
| R5 | Contract AUTO-pool exclusion | AC-11 |

Mỗi slice: test ĐỎ đúng lý do → implement tối thiểu → XANH → refactor.

## 8. Claim / ownership (O-9)

- Đổi branch `feat/kbs-vci-adjusted-param` → `feat/cafef-reference`; **cập nhật cùng lúc** dòng claim
  `docs/CLAIMS.md` (agent = `cafef-reference`) — nếu không preflight `claim-identity` chặn.
- Claim file list bổ sung: `vnbroker/common/client.py` (chưa có chủ), `vnbroker/reference/**`,
  `tests/unit/reference/**`, `tests/contract/**`.
- **Không** đụng `vnbroker/__init__.py` (F-01 claim), không đụng `common/data.py` (1823L, stale claim),
  không đụng `broker/`.

## 9. Baseline gate

`pytest <2 file adjusted>` 15 passed · `pytest tests/contract` 149 passed ·
`pytest tests/unit` 1 failed (version drift có sẵn)/2076 passed · ruff sạch ·
`check_all.ps1 -Quick` **CHƯA CHẠY** (thiếu `.venv`, không tự pip install).

## 10. Lệnh tái lập

```
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_xlsx_vs_json.py
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_cafef_compare.py
python C:\Users\Pham Viet Dung\AppData\Local\Temp\opencode\probe_factor_by_year.py
```

## 11. Rollback / Non-goals

Rollback: revert slice; xoá `vnbroker/reference/`; khôi phục helper fail-only trong 2 explorer.
Non-goals: bulk backfill tất cả mã, ghi DB, sửa frame provider, đụng broker/, đụng `__init__.py`.

## 12. Next steps

B4 đồng thuận → B5 claim (đổi tên) → B6 TDD → B7 gate → B8 re-audit → B9 bàn giao.
