# SUMMARY — S1/A1: nối 2 endpoint OHLCV của TCBS vào `quote.history()`

- **Worktree**: `C:\Mujoco Projects\tcbs-a1-bars`
- **Branch**: `feat/a1-bars` (không commit lên `dev`)
- **Base**: `bec8b824ef29df8ffb8a7805ef7e9f6a5dfdcac2`
- **Commit**: xem mục *Commit* bên dưới (ghi sau khi commit)
- **Nguồn spec**: `C:\Users\Pham Viet Dung\Downloads\openapi-v1.0.0.json`
  (`servers[0].url = https://openapi.tcbs.com.vn`)

> ⚠ **Lưu ý về `docs/PLAN_TCBS_REBUILD.md`**: task dẫn "10 AC chi tiết ở
> `docs/PLAN_TCBS_REBUILD.md` mục S1" nhưng **file này KHÔNG TỒN TẠI** trong
> worktree (đã `glob` toàn repo + kiểm tra cả repo chính). 10 AC được lấy từ
> chính message nhiệm vụ. Nếu plan đó tồn tại ở nơi khác, cần đối chiếu lại.

---

## 1. Commit

| | |
|---|---|
| Hash | `REPLACE_HASH` |
| Subject | `feat(tcbs): noi 2 endpoint OHLCV (bars + bars-long-term) vao quote.history()` |

Tái lập: `git -C "C:\Mujoco Projects\tcbs-a1-bars" log -1 --format=%H`

---

## 2. File đã đổi (đúng 5 file được phép)

| File | Trạng thái | Nội dung |
|---|---|---|
| `vnbroker/explorer/tcbs/bars.py` | **TẠO MỚI** (368L) | Toàn bộ logic 2 endpoint bars |
| `vnbroker/explorer/tcbs/const.py` | +16 | Chuyển `_TIMEFRAME_MAP` từ `quote.py` sang (AC8) |
| `vnbroker/explorer/tcbs/quote.py` | +28/−62 | Nối `bars.fetch_bars`, bỏ `NotImplementedError`, sửa docstring (AC5/6/10) |
| `tests/unit/explorer/tcbs/test_tcbs_bars.py` | **TẠO MỚI** (36 test) | Chứng minh 10 AC |
| `tests/unit/explorer/tcbs/test_tcbs_quote_history_not_implemented.py` | **XOÁ** (−30) | Mã hoá tuyên bố sai mà AC5 gỡ bỏ |

Xác nhận không đụng file nào khác:
```powershell
git -C "C:\Mujoco Projects\tcbs-a1-bars" status --short
```

---

## 3. Mapping 10 AC

| AC | Yêu cầu | Hiện thực | Test chứng minh |
|---|---|---|---|
| 1 | Cột đúng | `_STANDARD_COLUMNS` cố định + `pd.DataFrame(rows, columns=...)` | `test_bars_to_frame_returns_exactly_standard_columns` |
| 2 | tz-aware HCM, `tz_convert` **tường minh** | `bars.py:262` `.dt.tz_convert(_TZ)` | `test_bars_to_frame_time_column_is_tz_aware_ho_chi_minh`, `test_bars_to_frame_uses_tz_convert_not_tz_localize` |
| 3 | `2025-09-12T00:00:00Z` → `2025-09-12 07:00:00+07`, ngày không dịch | `pd.to_datetime(..., utc=True)` rồi `tz_convert` | `test_bars_to_frame_trading_date_is_same_day_in_vietnam_time` |
| 4 | Field lạ (`dataT1`) `.get()` an toàn | Mọi field đọc bằng `.get()`; `columns=` cố định | `test_unknown_server_field_data_t1_does_not_leak_into_frame`, `test_record_missing_optional_fields_yields_none_not_keyerror` |
| 5 | `history(1D, start≠end)` hết `NotImplementedError` | `quote.py` gọi `bars.fetch_bars` | `test_history_daily_multiday_no_longer_raises_not_implemented` |
| 6 | Sửa docstring sai ~347, ~421 | Sửa docstring `_compute_ohlc_from_intraday` + comment sai trong `history()` | `test_stale_claim_about_missing_bars_endpoint_is_gone` |
| 7 | Map D/W/M riêng, **không** dùng `_INTERVAL_MAP` | `_LONG_TERM_RESOLUTION` / `_INTRADAY_RESOLUTION` | `test_resolve_bars_endpoint_maps_interval` (8 case), `test_month_interval_never_maps_to_pandas_me` |
| 8 | `_TIMEFRAME_MAP` → `const.py` | Đã chuyển, `quote.py` import lại | `test_timeframe_map_lives_in_const_and_is_reexported_by_quote`, `test_bars_module_does_not_import_quote` |
| 9 | Không qua `_as_df`/`ohlc_to_df` | `bars.py` tự dựng frame; chỉ gọi `normalize_ohlc_prices` (không đụng `time`) | `test_bars_module_does_not_call_ohlc_to_df`, `test_bars_path_keeps_time_of_day_intraday` |
| 10 | `quote.py` ≤ 800L | **793L** (từ 801L) | `test_quote_module_stays_under_800_lines` |

### AC9 — vì sao không đi qua `ohlc_to_df`

Đọc code thật `vnbroker/core/utils/transform.py:399-408`:
- `:402` `df[col].dt.tz_localize(None)` — cắt tz
- `:406` `df[col].dt.date` — cắt giờ (khi `interval == "1D"`)

Cả hai đều phá tz-aware `Asia/Ho_Chi_Minh` và làm mất `HH:MM` của nến trong
phiên. `bars.py` gọi `tz_convert` **tường minh** rồi mới chuẩn hoá giá bằng
`transform.normalize_ohlc_prices` (hàm này chỉ đụng cột giá, không đụng `time`).

### AC2 — vì sao `tz_localize` là sai

`vnbroker/core/utils/normalizer.py:22-24` chỉ `tz_localize` khi cột `time`
**chưa có** tz. Nếu `bars.py` chỉ `tz_localize` thì frame UTC đi qua nguyên
vẹn → `00:00Z` thành `00:00+07` ⇒ **mất 7 giờ**, ngày giao dịch dịch chứ không
chỉ đổi nhãn UTC.

---

## 4. Test RED → GREEN (bằng chứng)

### 4.1 RED — trước khi có `bars.py`

Đã backup `bars.py` ra `%TEMP%`, xoá khỏi worktree, chạy test mới:

```
$ .venv\Scripts\python.exe -m pytest tests/unit/explorer/tcbs/test_tcbs_bars.py -q
ImportError: cannot import name 'bars' from 'vnbroker.explorer.tcbs'
============================== 1 error in 2.45s ===============================
```

Sau đó mới khôi phục `bars.py` và viết code. **Không dùng `git checkout --`**
để hoàn tác; dùng `git show HEAD:<file> > <file>` qua `cmd /c` (xem mục 8).

### 4.2 GREEN

```
$ .venv\Scripts\python.exe -m pytest tests/unit/explorer/tcbs/test_tcbs_bars.py -q
============================= 36 passed in 5.00s ==============================
```

### 4.3 Mutation check — chứng minh test KHÔNG rỗng

Thay `.dt.tz_convert(_TZ)` → `.dt.tz_localize(_TZ)` (chính là lỗi AC2 cảnh báo):

```
======================== 12 failed, 24 passed in 5.55s ========================
```

Test bắt được regression thật, không phải assert hình thức. Đã hoàn tác.

---

## 5. Gate — output thật

### 5.1 `ruff check vnbroker` — ✅ **PASS**
```
$ .venv\Scripts\python.exe -m ruff check vnbroker
All checks passed!
EXIT=0
```

### 5.2 `check_mypy_baseline.py` — ✅ **PASS**
```
$ .venv\Scripts\python.exe scripts/check_mypy_baseline.py
OK: no new strict errors (baseline 1266, now 1207, fixed 59).
Note: run with --update to shrink the baseline.
EXIT=0
```
⚠ **Không chạy `--update`** — baseline là file dùng chung, ngoài danh sách file
được phép sửa. 59 lỗi legacy đã bị sửa **tình cờ** (do đổi kiểu trong
`quote.py`); nên chạy `--update` ở PR riêng.

### 5.3 `pytest tests/` — ⚠ **4 test đỏ MỚI** (ngoài phạm vi file cho phép)

Lệnh:
```powershell
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
```

**Baseline thật đo được ở HEAD (không phải con số trong task):**
```
1 failed, 1492 passed, 30 skipped, 2 warnings in 136.43s
```
- 1 fail **có sẵn, không liên quan TCBS**: `tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible`
  → `AssertionError: khong thay DNSE_API_SECRET trong moi truong` (thiếu env var).

**Sau thay đổi:**
```
5 failed, 1522 passed, 30 skipped, 2 warnings in 131.83s
```
1522 − 1492 = **+30 test mới** (36 mới − 2 đã xoá = +34; 4 test đỏ mới ⇒ 1522 + 4 = 1526 ≈ khớp khi tính cả chênh lệch skip).

#### 4 test đỏ MỚI — nguyên nhân: **mock cũ mô phỏng SAI shape**

| Test | Mock cũ trả về |
|---|---|
| `test_quote_price_unit_consistency.py::..._in_vnd` | `{"t":"09:30:00","p":30400.0,...}` |
| `test_quote_price_unit_consistency.py::..._in_thousand_vnd` | như trên |
| `test_quote_price_unit_consistency.py::..._4_providers_stock_consistent_in_vnd` | như trên |
| `test_tcbs_parallel.py::test_tcbs_fetch_multiple_basic` | `{"t":..,"p":..,"v":..,"a":..}` ×4 |

Đây là shape **intraday tick** (`t`/`p`/`v`/`a`) của `/nyx/v1/intraday` —
chính xác contract mà **AC5 gỡ bỏ**. `bars_to_frame` đọc
`tradingDate`/`open`/`high`/`low`/`close`/`volume` theo spec, nên mock tick
⇒ **0 dòng** ⇒ `iloc[0]` ném `IndexError` / `assert not df.empty` fail.

**Bằng chứng đây là mock cũ chứ không phải bug code** — chạy lại đúng 3 assert
của test price-unit nhưng với payload **đúng shape spec**:
```
$ .venv\Scripts\python.exe -c "..."   # payload tradingDate/OHLC thật
price_unit = VND
close      = 30400.0
tz         = Asia/Ho_Chi_Minh
```
Cả 3 assert đều pass. ⇒ Code đúng; **fixture** sai.

#### Vì sao KHÔNG tự sửa
`tests/unit/api/test_quote_price_unit_consistency.py` và
`tests/unit/explorer/test_tcbs_parallel.py` **không nằm trong 5 file được
phép sửa**. Sửa chúng sẽ vi phạm chỉ dẫn phạm vi, nên **báo cáo để Owner /
coordinator quyết**, không tự ý đụng.

#### Đề xuất sửa (CHƯA làm — cần phê duyệt)
Đổi mock trong 2 file trên sang shape bars:
```python
{"open":30400.0,"high":30400.0,"low":30400.0,"close":30400.0,
 "volume":123456,"tradingDate":"2024-04-01T00:00:00Z"}
```
Sau đó chạy lại gate — dự kiến **1497+ passed, 30 skipped, 0 test đỏ mới**.

### 5.4 Gate CHƯA CHẠY

| Gate | Lý do |
|---|---|
| Test E2E / probe server TCBS thật | Cần JWT. Theo commit `b0dca5e`, Owner đã **revoke khóa API** + chủ động xoá fragment khỏa/OTP khỏi git; `docs/TCBS_CONNECTION_TEST_REPORT.md` đã lưu ý "sau revoke .env mất hiệu lực → cần API key MỚI + Smart OTP". **Không có credential ⇒ không có kết luận.** |
| Xác minh `countBack` đủ dùng thật | `_TRADING_DAY_RATIO = 0.70` và `_INTRADAY_BARS_PER_DAY` là **hệ số ước lượng**, chưa probe server. Đã ghi chú ngay trong `bars.py`. Rủi ro xem mục 7. |
| Xác minh `resolution` thật của `/nyx/v2/stock/bars` | Spec chỉ ghi "Bar timeframe in minutes (e.g. 60)". Bản đồ `1m→1, 5m→5, 15m→15, 30m→30, 1H→60` suy ra từ mô tả, **chưa** probe. |
| `pytest --update` mypy baseline | Ngoài 5 file cho phép. |
| Kiểm tra type thật của `coveredWarr` / `derivative` | `bars.py` chấp nhận đúng 4 giá trị trong spec; chưa có test với ticker thật loại đó. |

---

## 6. Vì sao baseline khác con số trong task

Task ghi *"Baseline phải giữ: 1497 passed, 26 skipped"*. **Đo thật ở HEAD cho
1492 passed / 30 skipped / 1 failed.** Chênh lệch có thể do:
- 4 test bị skip vì thiếu credential (JWT TCBS / DNSE);
- 1 test đỏ vì thiếu `DNSE_API_SECRET` trong môi trường.

Đã ghi lại **số đo thật** thay vì ép khớp con số. Tái lập:
```powershell
git -C "C:\Mujoco Projects\tcbs-a1-bars" stash list        # (không có thay đổi tạm)
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
```

---

## 7. Rủi ro

1. **[CAO] 4 test đỏ mới** chưa được xử lý (ngoài phạm vi file). Xem mục 5.3.
2. **[CAO] `countBack` là hệ số ước lượng, chưa probe.** Với khoảng ngày lớn,
   `countBack` có thể **thiếu** ⇒ thiếu nến ở đầu khoảng, hoặc **thừa** ⇒ tốn
   băng thông. Đã có trần `_MAX_COUNT_BACK = 20000` + `logger.warning` khi bị cắt,
   nhưng **cắt là âm thầm mất dữ liệu** (chỉ có log).
3. **[TRUNG BÌNH] `_end_epoch` lấy 23:59:59 giờ VN.** Đúng cho nến ngày, nhưng
   với nến phút của ngày hôm sau, `to` chỉ chặn ở cuối ngày ⇒ đúng.
   Rủi ro thật nằm ở việc server **làm tròn** `to` theo độ phân giải.
4. **[TRUNG BÌNH] `_long_history` (khoảng > 365 ngày) vẫn gọi `history()` theo
   từng năm.** Đã phải sửa filter `df['time']` thành tz-aware (trước đó so
   sánh tz-aware với chuỗi ngày trần ⇒ `TypeError`). Chưa có test cho nhánh này.
5. **[THẤP] `quote.py` = 793L**, dưới trần 800L nhưng sát. Thêm logic sẽ vượt.
6. **[THẤP] `bond` bị từ chối có chủ đích.** `get_asset_type` trả `'bond'` cho
   trái phiếu, nhưng spec `openapi-v1.0.0.json` **không liệt kê** `bond` ⇒ ném
   `ValueError` rõ ràng thay vì đoán. Cần xác nhận với Owner.

---

## 8. Bài học

1. **`git show HEAD:<file> > <file>` trong PowerShell hỏng encoding.**
   `Out-File -Encoding utf8` / `>` của PowerShell làm hỏng tiếng Việt có dấu
   (`Mã CP` → `M├ú CP`), tạo diff 49 dòng giả. Phải dùng `cmd /c` để redirect
   byte thô:
   ```powershell
   cmd /c 'cd /d "C:\Mujoco Projects\tcbs-a1-bars" && git show HEAD:vnbroker/explorer/tcbs/quote.py > vnbroker\explorer\tcbs\quote.py'
   ```
   Sau đó **kiểm tra `git diff --stat` phải rỗng** trước khi làm việc.

2. **Test spy trên `pd.Series.dt` không bắt được gì.** `pd.Series.dt` là
   descriptor; `patch.object(pd.Series.dt, ...)` im lặng không chặn. Phải patch
   `pandas.core.indexes.accessors.DatetimeProperties` (lớp thật, không phải lớp
   cha `CombinedDatetimelikeProperties`). Test đã **tự lộ** điều này khi fail
   với `calls == []`.

3. **Test "không được gọi hàm X" phải quét AST, không grep chuỗi.** Docstring
   `bars.py` nhắc `transform.ohlc_to_df` để giải thích AC9 — grep thô báo
   "đã gọi ohlc_to_df" ⇒ **báo động giả ngược**. Dùng `ast.walk()` lấy tên hàm
   thực sự được `Call`.

4. **`InstrumentType` nằm ở `vnbroker.core.utils.parser`, KHÔNG phải
   `vnbroker.core.models`.** `models.py` chỉ có `TickerModel`,
   `PaginationModel`, `FinancialReportModel`. Đoán sai ⇒ `ImportError` ngay.

5. **Test cũ mô phỏng contract đã chết là nguồn đỏ giả.** 4 test fail vì mock
   trả shape intraday tick. Trước khi sửa code, hãy **nạp payload đúng shape spec
   vào đúng assert đó** để chứng minh code đúng — như đã làm ở mục 5.3. Không
   có bước này thì dễ sửa nhầm code hoặc nới `bars_to_df` để "chiều mock",
   làm hỏng AC1/AC4.

6. **Baseline phải đo trước khi sửa.** Con số trong task (1497/26) lệch với thực
   tế (1492/30/1). Không có baseline đo được thì không phân biệt được "test đỏ
   mới" với "test đỏ có sẵn".

---

## 9. Tái lập toàn bộ

```powershell
$wt = "C:\Mujoco Projects\tcbs-a1-bars"

# 1. Test riêng của lát cắt
& "$wt\.venv\Scripts\python.exe" -m pytest tests/unit/explorer/tcbs/test_tcbs_bars.py -q --timeout=300 -p no:cacheprovider
#   -> 36 passed

# 2. Gate đầy đủ
& "$wt\.venv\Scripts\python.exe" -m pytest tests/ -q --timeout=300 -p no:cacheprovider
#   -> 5 failed, 1522 passed, 30 skipped   (1 pre-existing + 4 do mock cũ)

# 3. ruff
& "$wt\.venv\Scripts\python.exe" -m ruff check vnbroker
#   -> All checks passed!   (exit 0)

# 4. mypy baseline
& "$wt\.venv\Scripts\python.exe" scripts/check_mypy_baseline.py
#   -> OK: no new strict errors (baseline 1266, now 1207, fixed 59).   (exit 0)

# 5. AC10 — đếm dòng quote.py
(Get-Content -Encoding utf8 "$wt\vnbroker\explorer\tcbs\quote.py").Count
#   -> 793   (<= 800)

# 6. Phạm vi thay đổi
git -C $wt status --short
git -C $wt show --stat HEAD
```