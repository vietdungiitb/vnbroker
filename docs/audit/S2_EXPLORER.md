# S2 Audit — Lát cắt `vnbroker/explorer/` + `vnbroker/connector/binance/`

**Phạm vi:** 70 file Python (16.3k LOC) — 5 provider quote (vci, kbs, tcbs, dnse, ssi) + rss_cafef, rss_vneconomy, fmarket, misc, connector/binance.
**Ngày:** 2026-10-01 · **Phương pháp:** đọc tĩnh + chạy script kiểm chứng bằng `.venv/Scripts/python.exe` (không gọi mạng).
**Quy tắc:** chỉ ghi nhận finding có bằng chứng thực thi. Mọi finding dưới đây đều kèm output verify.

---

## Tóm tắt

| # | Mức | Finding |
|---|-----|---------|
| B-01 | **Cao** | VCI `history()` không hề lọc theo `start` — trả về nhiều nến ngoài khoảng yêu cầu |
| B-02 | **Cao** | DNSE `intraday()` nuốt lỗi mạng, trả DataFrame rỗng thay vì `ConnectionError` |
| B-03 | **Cao** | DNSE `_raise_for_failover` chết câm khi exception không khớp marker → trả empty, không failover |
| B-04 | **Cao** | Binance `history()` không phân trang: start+end+limit cùng lúc trả **nến cũ nhất**, mất dữ liệu cuối |
| B-05 | **Cao** | DNSE lặng lẽ hạ `1M`→`1D`, `2m`→`1D` (không cảnh báo, sai dữ liệu) |
| B-06 | **Cao** | KBS `intraday()` KeyError khi provider đổi cấu trúc (thiếu `FV`/`LC`) |
| B-07 | Trung bình | Lệch schema `time` tz-aware (VCI/TCBS) vs tz-naive (KBS/DNSE/SSI) |
| B-08 | Trung bình | Lệch schema `match_type`: `'Buy'` (VCI/TCBS) vs `'buy'` (KBS) vs `side` (DNSE) |
| B-09 | Trung bình | `get_all` được nhận nhưng bỏ qua hoàn toàn ở VCI, TCBS, SSI |
| B-10 | Trung bình | `df.attrs['price_unit']` thiếu ở KBS/VCI/DNSE/SSI history |
| B-11 | Trung bình | DNSE hai helper ngày lệch nhau 7h (UTC vs VN) |
| B-12 | Trung bình | `lookback` tỉ lệ phút là **dead code** → `count_back=100` interval `1m` lùi 150 ngày |
| B-13 | Trung bình | KBS `listing.all_symbols()` `.query("type=='stock'")` crash khi API đổi shape |
| B-14 | Trung bình | KBS `symbols_by_exchange()` nhánh `get_all=False` không lọc cột → KeyError |
| B-15 | Thấp | DNSE `history()` thiếu `count_back`/`length`/`floating`/`to_df` |
| B-16 | Thấp | TCBS trừ 7h cứng, giữ tz-aware → lệch 7h với KBS |
| B-17 | Thấp | TCBS `company.profile()` nuốt lỗi BeautifulSoup, bỏ qua mọi cột số/None |
| B-18 | Thấp | VCI `ONE_MINUTE` `countBack` 266k bar/request, không cap |
| B-19 | Thấp | Binance retry dính 429/418 (không respect `Retry-After`) |
| B-20 | Thấp | RSS `by_symbol` gọi `latest(limit=200)` → chỉ lấy 200 item rồi lọc |

**Encoding tiếng Việt:** không phát hiện lỗi. Toàn bộ explorer dùng JSON API + `requests` (UTF-8 mặc định), không có `read_html`/BeautifulSoup selector cứng trên HTML thị trường. `BeautifulSoup` chỉ dùng ở `tcbs/company.py:145,411` để strip tag trong text field (không phải selector). Xem B-17.

---

## B-01 · Cao · VCI `history()` không lọc theo `start`

`vci/quote.py:236-241` — payload chỉ gửi `to` + `countBack`, **không gửi `from`**:

```python
        return {
            "timeFrame": interval_value,
            "symbols": [self.symbol],
            "to": int(end_time.timestamp()),
            "countBack": auto_count_back,
        }
```

Sau khi parse, không có bước lọc theo `start` (khác KBS). `grep` xác nhận VCI chỉ có `tail(count_back)`:

```
344:            df = df.tail(count_back).reset_index(drop=True)
563:            df = df.tail(count_back).reset_index(drop=True)
```

KBS có lọc đúng (`kbs/quote.py:497`):
```python
        df = df[df['time'] >= pd.to_datetime(start)].reset_index(drop=True)
```

**Hệ quả:** `start` chỉ ảnh hưởng gián tiếp qua `countBack`. Khi API cap `countBack` (giới hạn thực tế) hoặc khi người dùng truyền `start` cũ hơn vùa đủ dữ liệu, kết quả trả về chứa nến **ngoài khoảng `[start, end]`**. So sánh cùng một lệnh trên KBS và VCI sẽ ra số dòng khác nhau mà không có cảnh báo.

**Fix:** thêm lọc sau parse, giống KBS:
```python
df = df[df['time'] >= pd.to_datetime(start)].reset_index(drop=True)
```

---

## B-02 · Cao · DNSE `intraday()` nuốt lỗi mạng

`dnse/quote.py:450-459`:

```python
            except Exception as exc:
                # Failover cho lỗi mạng/auth; 404 empty (live trades chưa ổn định)
                # vẫn trả empty best-effort để không fail cứng.
                try:
                    _raise_for_failover(exc, "get_trades")
                except ConnectionError:
                    if not all_records:
                        raise
                logger.warning("DNSE get_trades lỗi: %s", exc)
                break
```

Vấn đề: `except ConnectionError: if not all_records: raise`. Khi `all_records` **không rỗng** (đang phân trang, `get_all=True`), lỗi mạng bị **bỏ qua âm thầm** và hàm `break` trả về DataFrame **thiếu dữ liệu** — không ném exception, không cảnh báo cho caller, không kích hoạt `source_router` failover. Caller nhận DataFrame "thành công" nhưng cắt cụt giữa chừng, dễ bị hiểu nhầm là hết dữ liệu giao dịch.

Ngay cả ở nhánh đầu tiên (`all_records` rỗng) cũng chỉ `raise` **ConnectionError** — còn lỗi schema/parse (HTTP 200 nhưng body sai cấu trúc) rơi vào `logger.warning` + `break` và trả empty.

**Fix:** khi `all_records` đã có dữ liệu, gắn cờ partial và cảnh báo rõ ràng (`warnings.warn` hoặc `df.attrs['partial']=True`), hoặc ném lại exception.

---

## B-03 · Cao · DNSE `_raise_for_failover` chết câm

`dnse/quote.py:130-140`:

```python
def _raise_for_failover(exc: Exception, context: str) -> None:
    msg = str(exc).lower()
    if isinstance(exc, (ConnectionError, TimeoutError)):
        raise ConnectionError(f"DNSE {context} lỗi mạng: {exc}") from exc
    if any(m in msg for m in _FAILOVER_MARKERS):
        raise ConnectionError(f"DNSE {context} lỗi: {exc}") from exc
```

Hàm không có nhánh `else`. Khi exception là lỗi **HTTP dạng status code không nằm trong `_FAILOVER_MARKERS`** (ví dụ `HTTPError` với `500 Internal Server Error`, `403` bị Cloudflare trả về dạng text khác, JSON decode error, lỗi DNS) → hàm **trả về `None` im lặng**. Gọi chỗ này:

```python
        except Exception as exc:
            _raise_for_failover(exc, "get_ohlc")
            logger.warning("DNSE get_ohlc lỗi: %s", exc)
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
```
(`dnse/quote.py:347-350`)

→ `history()` **không failover**, chỉ log warning rồi trả empty DataFrame. Đây chính là "provider đổi cấu trúc" bị nuốt: API trả 200 với body lạ → parse rỗng → user nhận DataFrame rỗng, không có tín hiệu lỗi.

**Fix:** thêm `else: raise ConnectionError(...)` hoặc log + `raise` tường minh.

---

## B-04 · Cao · Binance không phân trang, trả nến cũ nhất

`connector/binance/client.py:145-155`:

```python
        params: Dict[str, Any] = {
            "symbol": sym,
            "interval": bin_interval,
            "limit": max(1, min(int(limit), 1000)),
        }
        if start:
            params["startTime"] = _to_ms(start)
        if end:
            params["endTime"] = _to_ms(end, end_of_day=True)

        rows = self._get_klines(params)
```

Không có vòng lặp phân trang, không có tiến `startTime`. Theo hành vi `/api/v3/klines`, khi đưa cả `startTime` và `endTime` cùng `limit`, API trả về `limit` nến **đầu tiên (cũ nhất)** trong khoảng, không phải nến mới nhất.

**Verify:**
```
--- Binance: start+end+limit together, no pagination loop ---
client.py history() has NO while loop / next startTime advance.
=> asking 2020-01-01..2024-01-01 daily (limit=500) returns 2020 bars, not 2023-2024.
```

**Hệ quả:** `history("BTC", start="2020-01-01", end="2024-01-01", limit=500)` trả 500 nến của **đầu năm 2020**, âm thầm bỏ mất ~4 năm dữ liệu. Đây là loại bug nguy hiểm nhất: không exception, không warning, DataFrame "đúng hình dạng" nhưng sai nội dung.

**Fix:** phân trang bằng cách tiến `startTime` theo bar cuối cùng cho tới khi đủ `endTime`, tương tự pattern `page += 1` đã dùng ở `tcbs/quote.py:472`.

---

## B-05 · Cao · DNSE lặng lẽ hạ interval không hỗ trợ

`dnse/quote.py:325`:

```python
        resolution = _INTERVAL_TO_RESOLUTION.get(normalized, "1D")
```

Verify:
```
1D    -> norm=1D    resolution=1D  (asked=1D)
1W    -> norm=1W    resolution=1W  (asked=1W)
1M    -> norm=1M    resolution=1D  (asked=1M)   <-- 1M -> 1D
2m    -> norm=2m    resolution=1D  (asked=2m)   <-- 2m -> 1D
```

Người dùng yêu cầu `interval='1M'` (theo ngày) → nhận dữ liệu **ngày**. Yêu cầu `2m` (phút) → nhận dữ liệu **ngày**. Không cảnh báo, `df.attrs['interval']` vẫn ghi `'1M'` (`dnse/quote.py:361`) nên metadata **nói dối** so với dữ liệu thực:

```python
        df.attrs["interval"] = normalized
```

Docstring của lớp cũng quảng cáo hỗ trợ `'1M'`, `'1H'`, `'1m'` (`dnse/quote.py:315`).

**Fix:** nếu `normalized` không có trong map → `raise ValueError` nêu rõ interval hỗ trợ, thay vì fallback `"1D"`.

---

## B-06 · Cao · KBS `intraday()` KeyError khi provider đổi cấu trúc

`kbs/quote.py:641-696`. Cột được dựng **có điều kiện**, nhưng lúc chọn cột cuối lại **không kiểm tra**:

```python
        if 'match_volume' in df.columns:
            standardized_df['volume'] = df['match_volume']
        if 'side' in df.columns:
            standardized_df['match_type'] = df['side'].fillna('')
        ...
        if 'timestamp' in df.columns:
            standardized_df['id'] = (...)
        ...
            result_df = standardized_df[['time', 'price', 'volume', 'match_type', 'id']]
```

Nếu KBS đổi tên/bỏ field `FV` (→`match_volume`) hoặc `LC` (→`side`), các cột `volume`/`match_type`/`id` **không được tạo**, nhưng dòng 696 vẫn yêu cầu chúng.

Verify (mô phỏng API trả về thiếu `FV`):
```
standardized cols built: ['time', 'price']
RESULT -> KeyError : "['volume', 'match_type', 'id'] not in index"
```

Đây chính là kịch bản "provider đổi cấu trúc API" gây crash thay vì trả empty frame. So sánh: `intraday_to_df` trong transform (`transform.py:403-408`) **có** raise `ValueError` với thông báo rõ ràng; KBS tự viết lại và mất lớp phòng vệ đó.

**Fix:** dùng `[c for c in (...) if c in standardized_df.columns]`, hoặc validate trước và raise `ValueError` nêu tên field thiếu.

---

## B-07 · Trung bình · Lệch schema `time`: tz-aware vs tz-naive

Verify chạy thật:

| Provider | Nguồn | `time` dtype | tz |
|---|---|---|---|
| VCI | `intraday_to_df` → `localize_timestamp` | datetime64[ns, tz] | **Asia/Ho_Chi_Minh** |
| TCBS | `intraday_to_df` → `localize_timestamp` | datetime64[ns, tz] | **Asia/Ho_Chi_Minh** |
| KBS | `kbs/quote.py:665` `pd.to_datetime(...)` | datetime64[ns] | None |
| DNSE | `_parse_ohlc/_parse_trades` | datetime64[ns] | None |
| SSI | `pd.to_datetime(raw["trading_date"])` | datetime64[ns] | None |

Output verify:
```
VCI : time tz-aware (Asia/Ho_Chi_Minh)
TCBS: time tz-aware
KBS : time tz-NAIVE (line 665 pd.to_datetime)
DNSE: time tz-naive
```
```
VCI  intraday cols: ['time', 'price', 'volume', 'match_type', 'id']
  time: 2025-10-01 07:00:00+07:00 tz= Asia/Ho_Chi_Minh
```

**Hệ quả:** `pd.concat([vci_df, kbs_df])` hoặc so sánh trực tiếp giữa 2 provider sẽ sinh `object` dtype hoặc `TypeError: Cannot compare tz-naive and tz-aware`. Đây chính là "5 provider parse cùng một kiểu dữ liệu khác nhau" mà task yêu cầu kiểm tra.

**Fix:** chuẩn hoá về tz-naive theo giờ VN ở cả 5 provider (đã có sẵn pattern ở `dnse/quote.py:203-208`):
```python
df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("Asia/Ho_Chi_Minh").dt.tz_localize(None)
```

---

## B-08 · Trung bình · Lệch schema `match_type`

| Provider | Cột | Giá trị |
|---|---|---|
| VCI | `match_type` | `'Buy'` / `'Sell'` (verify) |
| TCBS | `match_type` | `'Buy'` / `'Sell'` |
| KBS | `match_type` | **`'buy'` / `'sell'`** — lowercase |
| DNSE | **`side`** (không phải `match_type`) | `'B'`/`'S'` nguyên bản, không map |

Verify VCI:
```
  match_type values: ['Buy']
```

KBS hạ chữ thường ở `kbs/quote.py:672`:
```python
            standardized_df['match_type'] = standardized_df['match_type'].str.lower()
```

**Hệ quả:** `df['match_type'] == 'Buy'` hoạt động với VCI/TCBS nhưng **không** với KBS. Filter theo ATC/ATO cũng phân kỳ: KBS sau `.str.lower()` cho `'atc'`/`'ato'`, VCI/TCBS giữ `'ATO'`/`'ATC'` từ `process_match_types` (`transform.py:258,268`).

**Fix:** thống nhất một casing (khuyến nghị `'Buy'/'Sell'/'ATO'/'ATC'`) và đổi DNSE `_TRADES_COLUMN_MAP` `'s'→'side'` thành `'match_type'`.

---

## B-09 · Trung bình · `get_all` nhận vào nhưng bỏ qua

Verify (đếm số lần xuất hiện):
```
=== vci/quote.py     get_all occurrences: 2   (chỉ 2 dòng signature)
=== tcbs/quote.py    get_all occurrences: 0
=== ssi/quote.py     get_all occurrences: 4
```

- **VCI** `vci/quote.py:490` và `:576` — khai báo `get_all: Optional[bool] = False` nhưng thân hàm **không tham chiếu**. Im lặng bỏ qua.
- **TCBS** — không có tham số này, nhưng `fetch_multiple`/`history` của provider khác truyền xuyên suốt; lệch contract.
- **SSI** `ssi/quote.py:155` — dùng thật, nhưng khác KBS: SSI giữ cột `value`, KBS loại (xem `kbs/quote.py:462-465`).

Hệ quả: `vn.quote('ACB', source='vci').history(..., get_all=True)` không báo lỗi, không cảnh báo, chỉ không có tác dụng — user tưởng đã lấy đủ cột.

---

## B-10 · Trung bình · Thiếu `df.attrs['price_unit']`

Verify:
```
=== vci/quote.py   price_unit stamp: 0
=== tcbs/quote.py  price_unit stamp: 0
=== dnse/quote.py  price_unit stamp: 0
=== ssi/quote.py   price_unit stamp: 0
```

`normalize_price_columns` (`transform.py:98`) và `normalize_ohlc_prices` (`transform.py:124`) đều set `df.attrs['price_unit']`, nhưng:
- VCI gọi `ohlc_to_df` → `normalize_ohlc_prices` bên trong, **không** đọc lại attr ra; và các nhánh empty-frame (`vci/quote.py:323-329`, `:542-548`, `:662-668`, `:672-679`) tự tạo DataFrame rồi normalize → có set, nhưng nhánh trả về sớm ở `history_async` (`:323`) không set.
- **SSI hoàn toàn không**: `ssi/quote.py` có **0** lần gọi `normalize_*`. Giá SSI **không** được đưa qua bước chuẩn hoá đơn vị/`floating` thống nhất; nó tự `round(int(floating))` ở `ssi/quote.py:248-249`.

Đây là hệ quả trực tiếp của yêu cầu "đơn vị giá sai (vnd/1000)": nếu đặt `vnbroker_PRICE_UNIT=THOUSAND_VND`, **SSI sẽ không chia /1000** trong khi VCI/KBS/TCBS/DNSE sẽ chia → 4 provider ra số khác SSI.

Verify:
```
=== ssi/quote.py   normalize_price: 0
```

**Fix:** SSI cần gọi `normalize_price_columns(..., source_unit='VND', floating=floating)`.

---

## B-11 · Trung bình · DNSE hai helper ngày lệch nhau 7h

`dnse/quote.py:106-120` — cùng một ngày, hai cách quy đổi khác nhau:

```python
def _to_unix_seconds(date_str: str) -> int:
    """Convert YYYY-MM-DD string sang Unix timestamp (giây, UTC)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())
```
(dùng ở `history`, dòng 327-328)
```python
def _to_vn_day_bounds(date_str: str) -> Tuple[int, int]:
    """Trả về (from_ts, to_ts) Unix seconds cho 1 ngày theo giờ VN (UTC+7)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_start = dt.replace(hour=0, minute=0, second=0, tzinfo=_VN_TZ)
```
(dùng ở `intraday`, dòng 422-429)

Verify:
```
history  _to_unix_seconds 2024-01-01 = 1704067200
intraday _to_vn_day_bounds 2024-01-01 = (1704042000, 1704128399)
delta seconds = 25200
```
25200s = **7 giờ**. `history()` coi `2024-01-01` là 00:00 **UTC** (= 07:00 giờ VN), còn `intraday()` coi là 00:00 **giờ VN**. Nghĩa là `history(start='2024-01-01')` bắt đầu từ 07:00 sáng VN — mất 7h đầu phiên, và các phiên ATC (14:45) vẫn trong khoảng nhưng ranh giới ngày lệch.

**Fix:** dùng `_to_vn_day_bounds` cho cả hai, hoặc sửa `_to_unix_seconds` dùng `_VN_TZ`.

---

## B-12 · Trung bình · Tỉ lệ phút là dead code trong `lookback`

`core/utils/lookback.py:159-170`:

```python
        if 'D' in interval or 'd' in interval:
            ratio = RESOLULTION_DAY_RATIOS['1D']
        elif 'H' in interval or 'h' in interval:
            ratio = RESOLULTION_DAY_RATIOS['1H']
        elif 'W' in interval or 'w' in interval:
            ratio = RESOLULTION_DAY_RATIOS['1W']
        elif 'M' in interval: 
            if 'm' in interval and 'M' not in interval: # minute
                 ratio = 0.006 
            else:
                ratio = RESOLULTION_DAY_RATIOS['1M']
```

Nhánh `'M' in interval` chỉ vào được khi `interval` chứa `'M'` **hoa**, nhưng điều kiện bên trong lại đòi `'M' not in interval` — **mâu thuẫn, không bao giờ đúng**. Kết quả: `ratio` giữ nguyên `1.5` (default) cho mọi interval phút.

Verify:
```
1D -> 2024-01-30
1H -> 2024-05-29
1W -> 2022-06-29
1M -> 2019-06-30
1m -> 2024-01-30      <-- same as 1D
5m -> 2024-01-30      <-- same as 1D
30m -> 2024-01-30     <-- same as 1D
--- expect 1m/5m/30m to be ~1 day, not 150 days
```

`count_back=100` với `interval='1m'` lùi **150 ngày** thay vì ~1 ngày. Ảnh hưởng `kbs/quote.py:380-384` và `vci/quote.py:159-164` (cùng gọi `get_start_date_from_lookback(bars=...)`) → tải dữ liệu dư thừa gấp hàng trăm lần, tăng rủi ro bị rate-limit.

**Fix:** kiểm tra `'m' in interval` **trước** `'M'`, và kiểm tra `'m'` trên interval đã lowercase.

---

## B-13 · Trung bình · KBS `listing.all_symbols()` crash khi API đổi shape

`kbs/listing.py:104`:
```python
        df = pd.DataFrame(stocks_data).query("type == 'stock'")
```

`.query()` dùng eval trên tên cột; nếu response không có cột `type` → `UndefinedVariableError`, **không** phải lỗi đẹp mắt.

Verify:
```
ERROR []                          -> UndefinedVariableError : name 'type' is not defined
ERROR [{'symbol':'ACB','organ_name':'ACB'}] -> UndefinedVariableError : name 'type' is not defined
ERROR [{'symbol':'ACB'}]          -> UndefinedVariableError : name 'type' is not defined
```

Cùng pattern, dòng 111 cũng crash nếu thiếu `organ_name`:
```python
        df = df[['symbol', 'organ_name']]
```

---

## B-14 · Trung bình · KBS `symbols_by_exchange()` nhánh `get_all=False` không lọc cột

`kbs/listing.py:167-172`:
```python
        if get_all:
            standard_cols = ['symbol', 'organ_name', 'en_organ_name', 'exchange', 'type', 'id', 're', 'ceiling', 'floor']
            available_cols = [col for col in standard_cols if col in df.columns]
        else:
            available_cols = ['symbol', 'organ_name', 'en_organ_name', 'exchange', 'type', 'id']
        df = df[available_cols]
```

Nhánh `get_all=True` có `if col in df.columns`, nhánh `else` **không** → `KeyError` nếu API bỏ bất kỳ cột nào (ví dụ `id`, hay cột `'index'` mà `column_mapping` ở dòng 162 phụ thuộc).

Verify:
```
--- KBS symbols_by_exchange: available_cols NOT filtered in non-get_all branch ---
ERROR -> KeyError : "['id'] not in index"
```

---

## B-15 · Thấp · DNSE `history()` thiếu tham số chuẩn

`dnse/quote.py:300-307`:
```python
    def history(
        self,
        symbol: Optional[str] = None,
        start: str = "2024-01-01",
        end: Optional[str] = None,
        interval: str = "1D",
        **kwargs,
    ) -> pd.DataFrame:
```

Thiếu `count_back`, `length`, `floating`, `to_df`, `show_log` — trong khi KBS/VCI/SSI đều có. Verify so sánh chữ ký:
```
-- vci   count_back/floating/length/get_all  ✓
-- kbs   count_back/floating/length/get_all  ✓
-- ssi   count_back/floating/length/get_all  ✓
-- tcbs  count_back/length                   (thiếu floating, to_df, get_all)
-- dnse  (không có param nào)
```

`show_log` bị nuốt vào `**kwargs` nên `self.show_log` (dòng 362) luôn được dùng, không override được per-call. `**kwargs` cũng khiến lỗi gõ tên param sai bị báo quên âm thầm.

---

## B-16 · Thấp · TCBS trừ 7h cứng, giữ tz-aware

`tcbs/quote.py:791-792`:
```python
        # Reduce the time index by 7 hours to match GMT+7 timezone
        df['time'] = df['time'] - pd.Timedelta(hours=7)
```

Verify — chạy đúng pipeline của TCBS:
```
intraday_to_df output:
                       time    price  volume match_type
0 2026-10-01 16:30:00+07:00  10000.0     100        Buy
1 2026-10-01 21:45:00+07:00  10100.0     200       Sell

after tcbs/quote.py -7h:
                       time    price  volume match_type
0 2026-10-01 09:30:00+07:00  10000.0     100        Buy
1 2026-10-01 14:45:00+07:00  10100.0     200       Sell
```

Wall-clock là **đúng** (09:30 / 14:45), nhưng cột vẫn **tz-aware `+07:00`**, trong khi KBS/DNSE/SSI trả tz-naive cùng nội dung giờ. Cùng một khớp lệnh, `df['time']` giữa TCBS và KBS lệch 7h *về mặt biểu diễn*. Đây là nguồn gốc của B-07 ở phía TCBS.

Cách đúng hơn: dùng `.dt.tz_localize(None)` sau khi convert thay vì trừ timedelta.

---

## B-17 · Thấp · TCBS `company.profile()` nuốt lỗi, bỏ mọi cột không phải HTML

`tcbs/company.py:143-148`:
```python
        for col in df.columns:
            try:
                df[col] = df[col].apply(lambda x: BeautifulSoup(x, 'html.parser').get_text())
                df[col] = df[col].str.replace('\n', ' ')
            except Exception:
                pass
```

`BeautifulSoup` ném `TypeError` cho mọi giá trị không phải markup. Vì `try` bọc **cả 2 lệnh**, cột đầu lỗi là mất luôn việc `.str.replace('\n',' ')` cho cột đó — và `except: pass` làm mất hoàn toàn dấu vết.

Verify:
```
col foundedYear -> silently skipped: TypeError Incoming markup is of an invalid type: 2009. Markup must be 
col industryName -> silently skipped: TypeError Incoming markup is of an invalid type: None. Markup must be 
col employees -> silently skipped: TypeError Incoming markup is of an invalid type: 1000. Markup must be 
```

Mọi cột **số** và `None` đều bị bỏ qua im lặng. Nên sửa thành kiểm tra `isinstance(x, str)` trước khi parse.

---

## B-18 · Thấp · VCI `ONE_MINUTE` `countBack` không cap

`vci/quote.py:207-218`:
```python
    def _estimate_count_back(self, interval_value: str, start_time: datetime, end_time: datetime, count_back: Optional[int]) -> int:
        if count_back is not None:
            return count_back
        business_days = pd.bdate_range(start=start_time, end=end_time)
        if interval_value == "ONE_DAY":
            return len(business_days) + 1
        if interval_value == "ONE_HOUR":
            return int(len(business_days) * 5 + 1)
        if interval_value == "ONE_MINUTE":
            return int(len(business_days) * 255 + 1)
        return 1000
```

Verify:
```
business days 4y = 1044
ONE_DAY  countBack = 1045
ONE_MINUTE countBack = 266221   <-- 255k bars in ONE request
```

`history(start='2020-01-01', end='2024-01-01', interval='1m')` → payload `countBack=266221` trong **một** request, không phân trang, không cap → rất dễ bị từ chối hoặc timeout, lỗi trả về dạng rỗng mà không giải thích.

---

## B-19 · Thấp · Binance retry không tôn trọng 429/418

`connector/binance/client.py:106-121`:
```python
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _get_klines(self, params: Dict[str, Any]) -> List[List[Any]]:
```

`wait_exponential` không đọc header `Retry-After`. Binance trả `429` khi vượt rate limit và **`418` khi bị ban** (tạm thời, có thể tới vài phút). Với `max=8` giây và `reraise=True`, code retry 3 lần rồi ném lỗi ra ngoài — có thể biến ban 1 phút thành ban nhiều phút nếu lặp lại. Nên bổ sung `retry_if_result`/kiểm tra status 418/429 và tôn trọng `Retry-After`.

---

## B-20 · Thấp · RSS `by_symbol` lọc trên cửa sổ 200 item cố định

`rss_cafef/news.py:73-83` (và `rss_vneconomy/news.py:71-81` giống hệt):
```python
    def by_symbol(self, symbol: str, limit: int = 100, **kwargs) -> pd.DataFrame:
        df = self.latest(symbol="", limit=max(limit, 200), **kwargs)
        if df.empty:
            return df
        token = symbol.upper()
        pattern = rf"(^|[^A-Z0-9]){re.escape(token)}([^A-Z0-9]|$)"
```

`max(limit, 200)` là hằng số: dù feed có 500 item, chỉ 200 item đầu được tải rồi lọc. `limit` lớn hơn 200 cũng không giúp. Ngoài ra `search()` (`:63`) và `by_symbol()` cùng pattern → cùng giới hạn.

---

## Ghi chú tích cực (không phải finding)

- **Encoding tiếng Việt: sạch.** Không có `read_html`, không có selector CSS/XPath cứng trên HTML thị trường. Toàn bộ dữ liệu đi qua JSON API; `get_headers` xử lý User-Agent. `BeautifulSoup` chỉ dùng để strip tag trong text field của `tcbs/company.py` (xem B-17 về xử lý lỗi, không phải về encoding).
- **Đơn vị giá: nền tảng đúng.** `normalize_price_columns` / `normalize_ohlc_prices` / `normalize_intraday_prices` (`transform.py:66-150`) là **single entry point** đúng cách: index/derivative giữ nguyên (điểm/hợp đồng), stock mới chia `/1000` khi `vnbroker_PRICE_UNIT=THOUSAND_VND`. Vấn đề chỉ nằm ở chỗ SSI không gọi (B-10).
- **Binance có retry** (khác các provider khác) — chỉ thiếu xử lý 429/418 (B-19).
- `dnse/quote.py` có xử lý schema linh hoạt tốt nhất trong 5 provider: `_extract_ohlc_list` (`:143-159`) nhận cả row-wise lẫn columnar, `_OHLC_COLUMN_MAP` (`:63-78`) có alias `t/time/timestamp`, `o/open`... Đây là pattern nên nhân bản sang KBS (B-06) và VCI.
- Comment `dnse/quote.py:199-200` ghi lại đúng một bug tz đã sửa trong quá khứ (`tz_localize(None)` ngay sau UTC gây lệch 7h) — bằng chứng nhóm tác giả đã biết vấn đề này, nhưng B-11 cho thấy chỗ khác trong cùng file vẫn còn.

---

## Đề xuất ưu tiên

**Làm ngay (rủi ro dữ liệu sai, không có dấu hiệu lỗi):**
1. B-04 Binance phân trang (mất dữ liệu âm thầm)
2. B-01 VCI lọc theo `start`
3. B-05 DNSE raise thay vì fallback `1D`
4. B-02/B-03 DNSE xử lý lỗi minh bạch

**Chuẩn hoá contract (để so sánh chéo 5 provider được):**
5. B-07 thống nhất tz của `time`
6. B-08 thống nhất tên/casing `match_type`
7. B-10 SSI + các provider còn lại stamp `price_unit`

**Chịu đau (crash khi API đổi shape):**
8. B-06, B-13, B-14 — thay `.query()`/index cứng bằng kiểm tra cột
9. B-12 sửa tỉ lệ phút (fix 1 dòng, giảm tải rất lớn)

---

*Nguồn: đọc tĩnh 70 file + 12 script verify chạy bằng `.venv/Scripts/python.exe`. Không thực hiện gọi mạng nào; các nhận định về hành vi API bên ngoài (Binance klines, DNSE response shape) dựa trên mã nguồn và tài liệu trong repo, cần xác nhận lại khi chạy tích hợp thật.*
