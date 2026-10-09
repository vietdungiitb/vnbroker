# AUDIT ĐỘC LẬP — `docs/PLAN_TCBS_REBUILD.md`

**Vai trò:** auditor chỉ đọc, không sửa file nào ngoài file báo cáo này.
**Đối tượng:** `docs/PLAN_TCBS_REBUILD.md` (111 dòng) tại `docs/plan-tcbs @ 3176e27`.
**Nguồn đối chiếu:** `openapi-v1.0.0.json` (136.199 B), `tcbs-openapi-v1.0.0.postman_collection.json` (55.904 B).
**Baseline đo lại tại `3176e27`:** pytest `1497 passed, 26 skipped` · `ruff check vnbroker` exit 0 · `check_mypy_baseline.py` exit 0 · `ruff check tests` exit 1, **13 lỗi** (khớp PLAN §0). Mọi khẳng định dưới đây đo lại được.

---

## 0. Tóm tắt

Cả **3 tiền đề** kế hoạch dựa vào đều **đúng** (nhiệm vụ 1). Vấn đề không nằm ở tiền đề mà ở **AC và ranh giới lát**:

| # | Vấn đề | Mức |
|---|---|---|
| 1 | AC S3#5 "35 path còn lại" — đo được **37** | Sai số |
| 2 | PLAN **không** chứa tuyên bố bỏ Giai đoạn 0; không có mục rủi ro; không có chữ "chưa verify" | Lừa dối tiềm tàng |
| 3 | `stream.py` (170L) gọi `websocket.py` nhưng **không claim** của a2 | Cắt lát hỏng |
| 4 | `client.py` (689L, 17 wrapper) gọi method a3 xoá nhưng **không claim** của a3 | Cắt lát hỏng |
| 5 | Xoá `/aion/v1/accounts` làm hỏng `@abstractmethod get_account_list` | Hợp đồng vỡ |
| 6 | AC S1#3 (`07:00+07:00`) **không khả thi** qua `_as_df` | AC không thực thi được |
| 7 | `_TIMEFRAME_MAP` nằm trong `quote.py` → `bars.py` import ngược tạo circular import | Cắt lát hỏng |
| 8 | 2 file test của a1 sẽ đỏ, không claim | Cắt lát hỏng |
| 9 | `const.py:19` `'1M' → 'ME'` sai spec (`M`), plan không nhắc | Sai lệch hợp đồng |
| 10 | AC S1#4 nhắc field `dataT1` — **0 lần xuất hiện** trong mọi tài liệu được cung cấp | Không truy nguồn được |

---

## 1. PHẢN BÁC 3 TIỀN ĐỀ

Công cụ dùng: `git grep -n` + `git grep -c` (không đọc lại tài liệu đã audit trước đó), script Python đối chiếu 2 file JSON.

### 1(a) `NotImplementedError` với lý do sai — **XÁC NHẬN**

```
$ git -C <repo> grep -n "NotImplementedError" -- vnbroker/explorer/tcbs/quote.py
vnbroker/explorer/tcbs/quote.py:346:            raise NotImplementedError(
vnbroker/explorer/tcbs/quote.py:420:            raise NotImplementedError(
```

Trích nguyên văn (`quote.py:344-352`):

```python
        # TCBS iFlash OpenAPI does not support multi-day daily OHLC bars
        if interval_key in ["1D", "1W", "1M"] and days > 0:
            raise NotImplementedError(
                "TCBS iFlash OpenAPI does not support historical multi-day daily/weekly/monthly OHLC bars. "
                "TCBS OpenAPI only provides intraday tick data for the current session. "
                "For historical daily/weekly/monthly OHLC data, please use source='VCI' or source='KBS' "
                "(e.g., vn.quote(symbol, source='VCI').history(...)). "
                "For intraday data on TCBS, use interval='1m', '5m', or quote.intraday()."
            )
```

Trích nguyên văn (`quote.py:419-426`), **giống hệt** 5 dòng message trên.

Spec nói ngược lại:

```
$ python -c "... json.load(openapi-v1.0.0.json) ..."
/nyx/v2/stock/bars-long-term | resolution: Bar type: D (1 day), W (1 week), M (1 month).
response properties: open, high, low, close, volume, tradingDate (ISO 8601, UTC)
```

**Kết luận:** tiền đề (a) đúng. Docstring sai, và nó **đang chủ động đẩy người dùng** sang provider khác.

Hệ quả cần ghi thêm (kế hoạch chưa nêu): `tests/unit/explorer/tcbs/test_tcbs_quote_history_not_implemented.py:10` khẳng định `pytest.raises(NotImplementedError, match="TCBS iFlash OpenAPI does not support")` — tức **mã hoá tuyên bố sai thành test**, xanh vĩnh viễn. AC S1#5 (#2 bắt buộc `fail trước, pass sau`) không nói phải xoá file này.

### 1(b) `websocket.py` gửi JSON thay vì text frame pipe — **XÁC NHẬN**

```
$ git grep -n "json.dumps|base64|split\(|send\(|auth|subscribe|unsubscribe|heartbeat" -- vnbroker/explorer/tcbs/websocket.py
websocket.py:107:  headers["Authorization"] = f"Bearer {self._jwt_token}"
websocket.py:173:  await self._require_ws().send(json.dumps(sub_msg))
websocket.py:192:  await self._require_ws().send(json.dumps(unsub_msg))
websocket.py:215:  await self._ws.send(json.dumps({"cmd": "ping"}))
websocket.py:254:  data = json.loads(raw)
websocket.py:396:  await self._require_ws().send(json.dumps(sub))
```

Grep riêng 5 chuỗi AC yêu cầu:

| Chuỗi | Số lần trong `vnbroker/` |
|---|---|
| `d\|a\|\|\|` (auth text frame) | **0** |
| `d\|s\|` (subscribe pipe) | **0** |
| `d\|p\|\|\|` (heartbeat pipe) | **0** |
| `d\|u\|` (unsubscribe pipe) | **0** |
| `base64` | **0** |
| `split(` trong `websocket.py` + `ws_models.py` | **0** |

Payload thực tế gửi đi là JSON thuần:
- `websocket.py:166-170` → `{"cmd":"subscribe","symbols":[…],"channels":[…]}`
- `websocket.py:187-191` → `{"cmd":"unsubscribe",…}`
- `websocket.py:215` → `{"cmd":"ping"}`
- `websocket.py:251-254` → parse bằng `json.loads(raw)` trên **toàn bộ** frame, không tách pipe

Điểm duy nhất đúng trong `websocket.py` là `ping_interval=None` (`:115`).

**Kết luận:** tiền đề (b) đúng.

⚠ **Rủi ro tiềm tàng trong AC S2:** 6/8 AC của lát này (`d|a|||`, `d|s|tk|bp+bi+…`, `d|p|||`, `d|33|15`, `s|<CH>`, channel ID `thesis/*`) **không xuất hiện trong 2 file tài liệu được cung cấp**:

```
$ python -c "đếm trong openapi-v1.0.0.json"
'd|a|||':0  'd|s|':0  'd|p|||':0  'd|u|':0  'd|0|':0  'base64':0  'pipeline':0  'bp+bi':0
$ python -c "đếm trong postman_collection.json"
'd|a|||':0  'd|s|':0  'd|p|||':0  'success':0  'base64':0  'bp+bi':0
postman: 53 request, 0 saved response, 15 body (toàn bộ là POST/PUT của REST)
```

Hai tài liệu chỉ mô tả **URL của 5 endpoint WebSocket** (`/ws/ouranos/v1/stream`, `/ws/aither`, `/ws/nesoi`, `/ws/thesis/v1/stream/normal`, `/ws/thesis/v1/stream/derivative`) — **không có message schema nào**. Điều này làm **AC S2#8 không thực thi được**: *"Test offline với frame thật lấy từ tài liệu"* — tài liệu không chứa frame nào để lấy. Đây là thiếu sót của kế hoạch, không phải của tài liệu.

### 1(c) 19 path legacy vắng ở CẢ HAI tài liệu — **XÁC NHẬN, và số "35" sai**

Script AST-parse `_PATHS` (không regex thô), chuẩn hoá `{param}`/`:param` → `:P`, in bảng:

```
file             L  key                                openapi  postman  legacy  path
account.py      34  profile                            YES      YES      -       /eros/v2/get-profile/by-username/{custodyCode}
account.py      35  balance                            YES      YES      -       /aion/v1/accounts/{accountNo}/cashInvestments
account.py      36  purchasing_power                   YES      YES      -       /aion/v1/accounts/{accountNo}/ppse
account.py      37  list_accounts                      NO       NO       YES     /aion/v1/accounts
account.py      39  erebos_v1_asset                    NO       NO       YES     /erebos/v1/account/asset
account.py      40  erebos_v1_available_balance        NO       NO       YES     /erebos/v1/account/available-balance
account.py      41  erebos_v1_portfolio_asset          NO       NO       YES     /erebos/v1/portfolio-asset
account.py      42  erebos_v1_portfolio_asset_token    NO       NO       YES     /erebos/v1/portfolio-asset/token
account.py      43  erebos_v1_portfolio_stock_statistic NO      NO       YES     /erebos/v1/portfolio/stock/{accountNo}/statistic
account.py      45  erebos_v2_asset                    NO       NO       YES     /erebos/v2/accounts/{accountNo}/asset
account.py      46  erebos_v2_available_balance        NO       NO       YES     /erebos/v2/accounts/{accountNo}/available-balance
account.py      47  erebos_v2_stock_statistic          NO       NO       YES     /erebos/v2/accounts/{accountNo}/stock-statistic
account.py      48  erebos_v2_orders_history           NO       NO       YES     /erebos/v2/accounts/{accountNo}/orders/history
account.py      49  erebos_v2_orders_matching          NO       NO       YES     /erebos/v2/accounts/{accountNo}/orders/matching
account.py      50  erebos_v2_withdraw                 NO       NO       YES     /erebos/v2/accounts/{accountNo}/withdraw
account.py      51  erebos_v2_deposit                  NO       NO       YES     /erebos/v2/accounts/{accountNo}/deposit
account.py      52  erebos_v2_dividend                 NO       NO       YES     /erebos/v2/accounts/{accountNo}/dividend
equity.py       46  orders                             YES      YES      -       /aion/v1/accounts/{accountNo}/orders
equity.py       47  order_detail                       YES      YES      -       /aion/v1/accounts/{accountNo}/orders/{orderID}
equity.py       48  order_history                      NO       NO       -       /aion/v1/accounts/{accountNo}/orders/history   <-- SAI PHAN LOAI
equity.py       49  matching_details                   YES      YES      -       /aion/v1/accounts/{accountNo}/matching-details
equity.py       50  se                                 YES      YES      -       /aion/v1/accounts/{accountNo}/se
equity.py       51  place_order                        YES      YES      -       /akhlys/v1/accounts/{accountNo}/orders
equity.py       52  modify_order                       YES      YES      -       /akhlys/v1/accounts/{accountNo}/orders/{orderId}
equity.py       53  cancel_orders                      YES      YES      -       /akhlys/v1/accounts/{accountNo}/cancel-orders
equity.py       55  ticker_commons                     YES      YES      -       /tartarus/v1/tickerCommons
equity.py       57  stop_limit_place                   NO       NO       YES     /erebos/v2/order/stop-limit
equity.py       58  stop_limit_orders                  NO       NO       YES     /erebos/v2/order/stop-limit/orders
equity.py       59  stop_limit_cancel                  NO       NO       YES     /erebos/v2/order/stop-limit/{orderId}/cancel
equity.py       60  stop_limit_modify                  NO       NO       YES     /erebos/v2/order/stop-limit/{orderId}
```

Đếm chéo lại toàn bộ `vnbroker/broker/tcbs` + `vnbroker/explorer/tcbs` bằng chuỗi literal (bỏ 2 hằng tổ hợp `/nyx/v1`, `/tartarus/v1` trong `const.py`):

```
A. endpoint TCBS tìm thấy                                  : 56
B.   có trong OpenAPI+Postman                              : 37
C.   KHÔNG có trong cả 2 tài liệu                          : 19
D. AC S3#1 "19 path bị xoá" -> đo được 19   KHOA
E. AC S3#5 "35 path còn lại" -> đo được 37   KHONG KHOA   <-- SAI 2
F. 19+35 theo plan = 54; đo được B+C = 56
```

⇒ **Tiền đề (c) đúng (19 path), nhưng AC S3#5 sai**: con số thật là **37**, không phải 35. Sai số này đến từ đâu: `AUDIT_TCBS_OPENAPI_20260926` §5.1 ghi "35/48 (73%)"; đo lại `code ∩ spec = 37`, `spec chưa dùng = 11` (không phải 13). AC viết lại con số của audit cũ mà không đo lại.

**Bằng chứng tăng cường** (không bắt buộc, nhưng có): 4 bản spec cũ hơn trong thư mục Downloads (`openapi.json`, `openapi (1..3).json`, đều *"iFlash Open API 1.0.0"*, 46 path) cũng **0/19** path legacy. Điều này làm mạnh giả thuyết "trước khi iFlash ra mắt" — nhưng **vẫn không phải bằng chứng server** (xem §4).

---

## 2. LÁT CÓ THẬT SỰ RỜI NHAU KHÔNG

Tập file mà 3 agent được claim (`CLAIMS.md:74-76`): ∅ — **đúng**. Nhưng tập file *được sửa* ∅ **không** đồng nghĩa tập file *bị phụ thuộc* ∅. Dưới đây là các phụ thuộc đo được.

### a1 — `explorer/tcbs/bars.py` (mới) + `quote.py`

| Phụ thuộc | Bằng chứng | File của agent khác? |
|---|---|---|
| `bars.py` cần `_TIMEFRAME_MAP` | Định nghĩa tại `quote.py:46-55`, **không** nằm trong `const.py`. PLAN §1 nói `quote.py` "chỉ ủy nhiệm" ⇒ `quote.py` sẽ `import bars` ⇒ `bars.py` import ngược `_TIMEFRAME_MAP` từ `quote.py` = **circular import** | Không, nhưng chính a1 tự gây |
| `bars.py` cần đổi `1M` | `const.py:19` `'1M': 'ME'` — spec `bars-long-term` chỉ nhận `D \| W \| M`. Gửi `ME` sẽ bị từ chối. `const.py` **không** nằm trong claim của a1, lại được import bởi 7 module khác | `const.py` — **không ai claim** |
| `bars.py` không được dùng `_as_df` | `_as_df` (`:372-393`) → `transform.ohlc_to_df` **xoá tz** (xem §3) | — |
| Test đỏ | `tests/unit/explorer/tcbs/test_tcbs_quote_history_not_implemented.py` (2 test, khẳng định raise) và `tests/unit/api/test_quote_price_unit_consistency.py:57,83,130` (3 test monkeypatch `vnbroker.explorer.tcbs.quote.client.send_request`) | 2 file test **không** nằm trong claim của a1 |

Điểm tốt đo được: `monkeypatch.setattr("vnbroker.explorer.tcbs.quote.client.send_request", …)` patch **đúng module object dùng chung**:
```
$ .venv\Scripts\python.exe -c "import vnbroker.explorer.tcbs.quote as q; from vnbroker.core.utils import client; print(q.client is client)"
True
```
⇒ nếu `bars.py` dùng `from vnbroker.core.utils import client` thì 3 test kia vẫn xanh. Nếu `bars.py` gọi `requests` trực tiếp thì đỏ. Kế hoạch không ràng buộc điều này.

### a2 — `explorer/tcbs/websocket.py` + `ws_models.py`

**`stream.py` (170L) không được claim nhưng gọi trực tiếp cả 2 file:**

```
stream.py:18:  from vnbroker.explorer.tcbs.websocket import StreamType, TCBSWebSocketClient
stream.py:11:  from vnbroker.explorer.tcbs.ws_models import (MatchingEvent, OHLC, OrderBook, OrderBookLevel, Ticker, Trade)
stream.py:47:  use_sit=self._use_sit,                       # truyền vào TCBSWebSocketClient
stream.py:68:  await client.subscribe(symbols, ["ohlc"])   # channel dạng TÊN
stream.py:71:  if msg.channel in ("ohlc", "candle") and isinstance(msg.data, OHLC):
stream.py:89/109/129:  subscribe(symbols, ["orderbook"] / ["ticker"] / ["trade"])
stream.py:150: use_sit=self._use_sit,
```

Ba xung đột với AC của a2:
1. **AC S2#7 "Xoá `_WS_ENDPOINTS_SIT`"** — nếu xoá luôn tham số `use_sit`, `stream.py:47,150` ném `TypeError`. Kế hoạch không nói có giữ tham số hay không.
2. **AC S2#3 subscribe theo pipe `d|s|tk|bp+bi+…`** — `stream.py:68,89,109,129` truyền tên channel `"ohlc"/"orderbook"/…`. Nếu a2 đổi tên channel sang channel ID thì 4 call này hỏng.
3. **AC S2#6 channel ID riêng cho `thesis/*`** — `stream.py` không có method nào cho `thesis`; `__init__.py:17-18` re-export `TCBSWebSocketClient`, `StreamType`, `TCBSStreamService` — cũng không claim.

**Và không có test nào bảo vệ:** `git grep -ln "TCBSStreamService|stream_matching|stream_ohlc" -- tests/` → **0 kết quả**. Việc hỏng sẽ **im lặng**.

### a3 — `broker/tcbs/account.py` + `equity.py`

**`client.py` (689L) không được claim nhưng gọi 17 method sẽ bị xoá:**

Đếm bằng AST trên `vnbroker/broker/tcbs/client.py`:

| Nhóm | Method | Dòng | Số dòng |
|---|---|---|---|
| `erebos/v1` | `get_erebos_v1_asset` … `…_portfolio_stock_statistic` | 161-179 | 19 |
| `erebos/v2` | `get_erebos_v2_asset` … `…_dividend_history` | 181-241 | 61 |
| `stop-limit` | `place_stop_limit_order`, `get_stop_limit_orders`, `cancel_stop_limit_order`, `modify_stop_limit_order` | 395-430 | 36 |
| | | | **102L / 17 method** |

Xoá method ở `account.py`/`equity.py` ⇒ `client.py:163,167,…,430` ném **`AttributeError` lúc runtime** (không phải lúc import ⇒ test collection vẫn xanh).

**Test sẽ đỏ — 29 test, không file nào trong claim của a3:**

```
tests/integration/tcbs/test_tcbs_full_acb.py         19 test
   :165-287  test_get_erebos_v1_asset … test_get_erebos_v2_dividend_history   (13)
   :399-459  test_place_stop_limit_order_dry_run, …_write_disabled,
             test_get_stop_limit_orders, test_cancel_stop_limit_order_dry_run,
             test_modify_stop_limit_order_dry_run                            (5)
   :611      test_client_has_all_new_methods  — assert hasattr cho cả 13+4 tên (1)
tests/unit/broker/tcbs/test_account_money.py         6 test
   :74-118   test_list_accounts_*  (path /aion/v1/accounts — nằm trong 19 legacy)
tests/unit/broker/tcbs/test_equity_derivatives.py    4 test
   :185-207  test_get_order_history_*  (path /aion/v1/accounts/{a}/orders/history)
TONG 29 test
```

Đo nền: `test_tcbs_full_acb.py` **42 passed, 4 skipped**; `test_account_money.py` **39 passed** (tại `3176e27`).

**Phụ thuộc import xuyên lát (an toàn, nhưng cần ghi):** `equity.py:41` và `money.py:28` đều `from vnbroker.broker.tcbs.account import _validate_account_no` (`account.py:924`). Nếu a3 tách `account.py` (PROPOSAL GĐ3 có gợi ý tách `account_legacy.py`) mà mang theo hàm này đi ⇒ **`money.py` hỏng**, và `money.py` không ở đâu trong claim.

### Tổng kết lát

| Lát | File được claim | File **bị phụ thuộc** mà không claim | Rủi ro |
|---|---|---|---|
| a1 | `bars.py`, `quote.py` | `const.py` (7 importer), 2 file test | Thấp–TB |
| a2 | `websocket.py`, `ws_models.py` | `stream.py` (170L), `__init__.py`, **0 test** | **Cao** |
| a3 | `account.py`, `equity.py` | `client.py` (689L), `money.py`, 3 file test / 29 test | **Cao** |

Kết luận §2: **"rời nhau" chỉ đúng ở tập file *được sửa*, sai ở tập file *bị ảnh hưởng*.** Đây là vấn đề cắt lát thật, cần nêu trước khi dispatch.

---

## 3. AC VỀ TIMEZONE

### 3.1 Chạy đúng đoạn yêu cầu

```
$ .venv\Scripts\python.exe -c "import pandas as pd; from vnbroker.core.utils.normalizer import Normalizer; df=pd.DataFrame({'time': pd.to_datetime(['2025-09-12T00:00:00Z'], utc=True), 'close':[1]}); print(Normalizer.normalize_history(df)['time'].dt.tz)"
UTC
```

⇒ **Kết quả là `UTC`.** `Normalizer` giữ nguyên tz đã gắn — `normalizer.py:20-24`:

```python
def _to_canonical_tz(series):
    if getattr(series.dt, "tz", None) is None:
        return series.dt.tz_localize(_canonical_tz())
    return series          # <-- đã tz-aware thì GIỮ NGUYÊN, không convert
```

Nếu `bars.py` trả frame đã là `+07:00` thì `Normalizer` không đụng tới. Nhưng nếu `bars.py` trả frame `UTC` thì `Normalizer` **không sửa** ⇒ AC S1#2 ("KHÔNG phải UTC") không tự động thoát.

**⇒ Đúng như tôi dự đoán: AC buộc phải gọi `tz_convert` tường minh trong `bars.py`.**

### 3.2 Kế hoạch có nói rõ chỗ này không? — **KHÔNG**

```
$ git grep -n "tz_convert|tz_localize|Asia/Ho_Chi_Minh|tz\b|Normalizer|bars.py" -- docs/PLAN_TCBS_REBUILD.md
28:  quote.py chỉ ủy nhiệm
36:  | a1 | … explorer/tcbs/bars.py (mới) …
52:  | 2 | time tz-aware Asia/Ho_Chi_Minh — KHÔNG phải UTC (bẫy đã đo: Normalizer giữ UTC) |
```

Dòng 52 **chỉ nêu bẫy, không nêu cách sửa**. Không có `tz_convert` trong cả kế hoạch. **Đây là thiếu sót.**

### 3.3 Nhưng vấn đề lớn hơn: AC S1#3 **không khả thi** qua đường `_as_df` sẵn có

Đo trên `transform.ohlc_to_df` với `source='TCBS'`, `tradingDate = "2025-09-12T00:00:00Z"` đã `tz_convert('Asia/Ho_Chi_Minh')`:

```
interval=1D  dtype=datetime64[ns]  tz=None  value=Timestamp('2025-09-12 00:00:00')   <-- mất 07:00
interval=1W  dtype=datetime64[ns]  tz=None  value=Timestamp('2025-09-12 07:00:00')
interval=1M  dtype=datetime64[ns]  tz=None  value=Timestamp('2025-09-12 07:00:00')
```

Nguyên nhân — `transform.py:396-408`:
```python
for col, dtype in dtype_map.items():          # _OHLC_DTYPE["time"] = "datetime64[ns]"
    if (dtype == "datetime64[ns]" and df[col].dt.tz is not None):
        df[col] = df[col].dt.tz_localize(None) # :402  CẮT TZ
    if col == 'time' and interval == "1D":
        df[col] = df[col].dt.date              # :406  CẮT GIỜ, chỉ còn ngày
    df[col] = df[col].astype(dtype)
```

Sau đó `Normalizer` gắn lại `+07:00` cho frame tz-naive:

```
qua _as_df interval=1D  -> Timestamp('2025-09-12 00:00:00')
   +Normalizer         -> Timestamp('2025-09-12 00:00:00+0700', tz='Asia/Ho_Chi_Minh')
```

**Đối chiếu AC:**

| AC | Nội dung | Đo được qua `_as_df` | Kết luận |
|---|---|---|---|
| S1#2 | `time` tz-aware `Asia/Ho_Chi_Minh` | frame sau `_as_df` là **tz-naive**; chỉ thành tz-aware ở tầng data layer | AC **đúng** nhưng kế hoạch **không nói kiểm ở tầng nào**. Kiểm ở `bars.py`/`quote.py` ⇒ đỏ |
| S1#3 | `2025-09-12T00:00:00Z` → `2025-09-12 07:00:00+07:00`, **ngày không dịch** | `1D` → `00:00:00+07:00` ❌ · `1W`/`1M` → `07:00+07:00` ✅ | AC **không khả thi cho `1D`** nếu dùng `_as_df` |

⇒ `bars.py` **buộc phải bypass `_as_df`** (dựng frame riêng, `tz_convert` rồi mới trả), hoặc AC S1#3 phải được viết lại thành "00:00 giờ VN cho `1D`". Kế hoạch **không đề cập** `transform.ohlc_to_df`, không đề cập `_as_df`, không đề cập `const.py:34-41` (`_OHLC_DTYPE`).

Lưu ý thêm: `tests/contract/test_layer_normalization.py:87-102` khẳng định *"naive được hiểu là GIỜ VIỆT NAM"* và `:74-84` khẳng định *"đã tz-aware thì KHÔNG dịch chuyển"*. Nếu `bars.py` trả **naive** thì `Normalizer` hiểu là giờ VN — nhưng TCBS spec nói `tradingDate` là **ISO 8601 UTC**, nên trả naive sẽ **lệch 7 tiếng**. AC S1#3 là hướng đúng; kế hoạch thiếu chỉ dẫn.

---

## 4. NGUYÊN TĮC CHỐNG LỪA DỐI

### 4.1 Tiền đề trong câu hỏi: PLAN §4 **không** chứa câu đó

Câu *"Giai đoạn 0 (probe 19 path) đã bị bỏ, Owner quyết xoá theo tài liệu"* **không nằm trong `PLAN_TCBS_REBUILD.md`**. Nó nằm ở `docs/CLAIMS.md:88-89`:

```
$ git grep -n "Giai đoạn 0|probe 19 path|Owner quyết" -- .
docs/CLAIMS.md:88:  **Cổng Giai đoạn 0 (probe 19 path) đã bị bỏ** — Owner quyết xoá theo tài liệu chính
docs/CLAIMS.md:89:  thức, không cần probe. Ghi rõ: **xoá theo quyết định Owner, chưa verify bằng server.**
```

Trong kế hoạch, §4 (dòng 85-89) là:

```
## 4. Ngoài phạm vi (không làm)
- GĐ4 TokenManager · GĐ5 13 endpoint còn lại — lát sau
- Viết lại broker/tcbs/derivatives.py (852L) — ngoài lát này
- Xoá _analysis/_stocks/_future URLs của domain cũ — ghi nhận, chưa đụng
```

Và kế hoạch **hoàn toàn không có** mục rủi ro:

```
$ git grep -n "OCP|Rủi ro|risk|an toàn|chưa verify|Owner|probe" -- docs/PLAN_TCBS_REBUILD.md
(hit duy nhất: "GĐ1", "GĐ2", "GĐ3", "GĐ4" — dòng 36,37,38,87)
```

### 4.2 Đánh giá

**Quyết định của Owner: hợp lý về mặt quản trị.** Owner là người quyết, không phải kế hoạch tự quyết. `PROPOSAL:433` đã ghi rõ rủi ro *"Xóa 19 path nhưng TCBS vẫn phục vụ | trung bình | **Hỏng tiền thật** | Cổng Giai đoạn 0 bắt buộc"* và `:473` *"**Không** bắt đầu Giai đoạn 3 trước khi có bảng probe"* — bỏ cổng là một **quyết định có chủ đích**, không phải sơ suất.

**Nhưng kế hoạch đang yêu cầu PASS cho thứ chưa verify — theo đúng nghĩa câu hỏi.** Ba dấu hiệu:

1. **AC S3#1 viết như sự thật đã xác lập:** *"19 path legacy bị xoá khỏi `_PATHS`"*. Người đọc AC không thấy đây là *quyết định của Owner trên giả định*, mà là *kết luận đã có bằng chứng*.
2. **AC S3#2 viết như sự thật đã xác lập:** *"**Không** còn path `erebos/v1`, `erebos/v2`, `aion/v1/accounts` … trong mã"*. Đây là mô tả hành vi sau khi sửa — viết dạng "không còn" dễ bị đọc thành "đã xác nhận không tồn tại trên server".
3. **Kế hoạch không mang disclaimer.** Cảnh báo *"chưa verify bằng server"* chỉ nằm ở `CLAIMS.md:89`. Agent đọc `PLAN_TCBS_REBUILD.md` (tài liệu được giao để làm việc) sẽ **không thấy** nó.

**Nguy cơ cụ thể, không suy đoán:** AC S3#3 (*"Method công khai gọi path đó **ném lỗi rõ ràng**"*) là biện pháp giảm thiểu đúng, nhưng `docs/SUMMARY_a3.md` (theo `PLAN:111`) sẽ được viết sau khi xoá xong. Không có dòng nào trong kế hoạch bắt agent ghi *"19 path vắng ở 2 tài liệu, chưa probe server"*. Đây là đúng cái mẫu bài học `PROPOSAL:420-421`: *"Test luôn xanh mà không chạm server là tự lừa mình."*

**Bằng chứng server hiện không thể lấy** (không phải lỗi kế hoạch, nhưng phải ghi rõ trong kế hoạch để người đọc không hiểu nhầm là "đã thử"):
- `AUDIT:354` — Giai đoạn 0 bị chặn vì token hết hạn; `401` chạy **trước routing** nên không phân biệt được "path tồn tại" / "path không có".
- Đo lại DNS: `openapi.tcbs.com.vn` → `103.4.129.48`; `openapisit.tcbs.com.vn` → chỉ trả `SOA tcbs.com.vn`, **không có bản ghi A** ⇒ không có môi trường test.
- Mẫu thời gian thêm: `git log -S` cho thấy `erebos_v2_*` và `stop_limit_*` được thêm ở `38eec3a` (**2026-09-22**), **sau** `b9207fb` *"rewrite entire library with official iFlash Open API paths"* (**2026-05-20**). ⇒ chúng **không phải tàn dư cũ** — chúng là phần thêm mới không có trong spec. Điều này làm yếu giả thuyết "xoá vì tài liệu nói vậy".

**Kết luận §4:** quyết định Owner **hợp lý**, nhưng kế hoạch **chưa nói rõ đây là quyết định dựa trên giả định, chưa kiểm chứng server** — và vì thiếu mục rủi ro, kế hoạch đang ngầm yêu cầu PASS cho một thứ **chưa verify được**.

---

## 5. CÁC PHẢN ĐỐI CẦN SỬA

| # | Phản đối | Bằng chứng | Sửa gì |
|---|---|---|---|
| **P1** | AC S3#5 "35 path còn lại" sai — đo được **37** | script: `code ∩ spec = 37`, `spec chưa dùng = 11` (không phải 13) | Sửa `35` → `37`; `19+35=54` → `19+37=56` |
| **P2** | Kế hoạch không có mục rủi ro; disclaimer "chưa verify server" chỉ ở `CLAIMS.md:89`, agent đọc plan không thấy | `git grep` plan: 0 hit "chưa verify/Owner/probe/rủi ro" | Thêm mục "Rủi ro đã biết" vào plan: xoá 19 path là **quyết định Owner theo 2 tài liệu, chưa probe server** (`401` trước routing không phân biệt được; SIT DNS không phân giải) |
| **P3** | AC S3#1/#2 viết như kết luận đã xác lập | `PLAN:77-78` | Chèn "(theo quyết định Owner, **chưa verify server**)" vào cả hai AC |
| **P4** | `stream.py` (170L) gọi `websocket.py`/`ws_models.py`, **không claim**, **0 test** | `stream.py:11,18,47,68,71,89,109,129,150`; `git grep -ln "TCBSStreamService" -- tests/` → 0 | Hoặc đưa `stream.py` vào claim a2, hoặc thêm AC S2#9 "giữ tương thích `stream.py`: `use_sit`, tên channel, chữ ký `subscribe`" |
| **P5** | `client.py` (689L) có **17 wrapper / 102 dòng** gọi method a3 xoá, **không claim** | `client.py:161-241, 395-430` | Đưa `client.py` vào claim a3 (và `money.py` nếu tách `account.py`) |
| **P6** | Xoá `/aion/v1/accounts` ⇒ `@abstractmethod get_account_list` mất implementation | `base.py:55-56` (abstract) → `client.py:122-129` → `client.py:147-149` → `account.py:110-155` | AC S3 mới: `get_account_list` phải **đổi nguồn dữ liệu** (vd `/aion/v1/customers/{custodyId}/accounts`, có trong spec) chứ không xoá |
| **P7** | AC S1#3 không khả thi cho `1D` qua `_as_df`; AC S1#2 không nói kiểm ở tầng nào | `transform.py:402` cắt tz, `:406` cắt giờ; đo: `1D → 00:00+07:00` | Thêm AC: "`bars.py` **không** dùng `_as_df`/`ohlc_to_df`; `tz_convert('Asia/Ho_Chi_Minh')` tường minh; kiểm tz ở **tầng data layer** sau `Normalizer`, không ở frame thô" |
| **P8** | `bars.py` ↔ `quote.py` circular import qua `_TIMEFRAME_MAP` | `_TIMEFRAME_MAP` ở `quote.py:46-55`, không có trong `const.py`; `PLAN:28` nói quote chỉ ủy nhiệm | AC S1 mới: chuyển `_TIMEFRAME_MAP` sang `const.py` — và **claim `const.py`** cho a1 |
| **P9** | `const.py:19` `'1M' → 'ME'` sai spec (`M`) | spec: `resolution: D (1 day), W (1 week), M (1 month)`; `const.py:19` | AC S1 mới: `bars.py` dùng map riêng `D/W/M`; **không** tái dùng `_INTERVAL_MAP` |
| **P10** | 29 test hiện có sẽ đỏ sau a3, **0 file** trong claim | đếm AST: `test_tcbs_full_acb.py` 19, `test_account_money.py` 6, `test_equity_derivatives.py` 4 | Đưa 3 file test vào claim a3 với nghĩa vụ xoá/sửa tương ứng |
| **P11** | 2 file test của a1 sẽ đỏ | `test_tcbs_quote_history_not_implemented.py` (2 test), `test_quote_price_unit_consistency.py:57,83,130` | Đưa vào claim a1; yêu cầu xoá file `not_implemented` |
| **P12** | AC S1#4 nhắc `dataT1` — **không có trong tài liệu nào** | đếm `dataT1`: `openapi-v1.0.0.json` = 0, postman = 0, `git grep dataT1 -- .` chỉ hit `PLAN:54` | Ghi rõ field lấy từ đâu; nếu không xác minh được thì đổi thành "mọi field không có trong spec phải `.get()`" (F6) thay vì nêu tên field cụ thể |
| **P13** | AC S2#8 "test offline với frame thật lấy từ tài liệu" **không thực thi được** | postman: 53 request, **0 saved response**; `d\|s\|`/`base64`/`bp+bi` = 0 ở cả 2 file | Cần nguồn frame thật (log live, hoặc tài liệu khác). Không có ⇒ AC phải ghi "CHƯA XÁC MINH", không phải "test bằng frame thật" |

---

VERDICT: NEED_REVISION

**Lý do:** 3 tiền đề đều đúng, nhưng kế hoạch hỏng ở 13 điểm đo được: AC S3#5 sai số (P1), thiếu mục rủi ro khiến plan yêu cầu PASS cho thứ chưa verify (P2, P3), 2 ranh giới lát cắt ngang file không claim và không test (`stream.py`, `client.py` — P4, P5), một hợp đồng abstract bị phá (P6), và 3 AC không thực thi được như đang viết (P7, P12, P13). Chưa nên dispatch 3 agent cho tới khi P1-P13 vào kế hoạch.