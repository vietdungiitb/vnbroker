# Kế hoạch xây dựng thư viện SSI native trong vnbroker — Full OpenAPI, hướng nguồn chính

> Trạng thái: **ĐÃ TRIỂN KHAI XONG P0 (S0–S8) ngày 2026-09-22** —
> 171 unit tests SSI + 3 snippet tests, SSI coverage 93%, mypy --strict + ruff sạch,
> full suite 700 passed / 0 failure. Bằng chứng: `artifacts/ssi-handover/`.
> P1–P3 (explorer/router/cutover) chưa làm.
> Trạng thái gốc khi lập plan: KẾ HOẠCH — CHƯA CODE.
> Nguyên tắc nền (không thương lượng):
> 1. **KHÔNG sử dụng `ssi-sdk`** dưới mọi hình thức dependency (`pip install ssi-sdk` bị cấm;
>    lệnh cài thử trước đây đã bị hủy — giữ nguyên).
> 2. **Clone/port code CHỈ khi cần thiết**, giới hạn ở wire-protocol facts (§1, §3),
>    viết lại toàn bộ theo chuẩn vnbroker (pandas in/out, `requests`, `tenacity`,
>    `BrokerSession`, `@write_gate`, `Redactor`).
> 3. Bao phủ **100% hàm OpenAPI mà SSI hỗ trợ** (bảng kiểm §1.2 — thiếu 1 endpoint = fail audit).
> 4. Thiết kế để SSI trở thành **nguồn chính của vnbroker** (lộ trình §5).
> Cơ sở xác minh: source công khai `SSI-Securities-Inc/ssi-sdk-python`
> (endpoint paths, payload schemas, RSA-sign, WS protocol — đã đối chiếu từng file) +
> chuẩn TCBS lane trong repo.

## 0. Phạm vi

### 0.1. Scope IN

- `vnbroker/broker/ssi/` native: `__init__, auth, account, money, equity, derivatives,
  market, portfolio, fco, stream, client, exceptions, _transport.py, _signing.py,
  _enums.py` (mirror `broker/tcbs/`, xem §2).
- `SSICredentialConfig` trong `vnbroker/broker/security/credentials.py`.
- `BrokerRegistry.register("ssi", SSIBrokerClient)` + `Vnbroker.broker(provider="ssi")`.
- Rate-limiter native (10 req/s default, theo SDK) + retry `tenacity` (thay retry custom của SDK).
- Unit tests mock `requests`/`websockets` (không mạng, không creds), docs, env mẫu, CHANGELOG.
- Phase 2 (§5): `vnbroker/explorer/ssi/` (Quote/Listing/Trading native, auth không OTP)
  + `source_router` primary pools + cutover SSI thành default.

### 0.2. Scope OUT

- Cấm dependency `ssi-sdk`; cấm copy-paste nguyên file SDK (chỉ port allowlist §3).
- Cấm thêm dependency mới: dùng `requests`, `websockets>=12.0`
  (**bắt buộc ≥12.0** — sync client `websockets.sync` chỉ tồn tại từ 12.0;
  pin hiện tại `>=11.0` resolve 11.x sẽ `ImportError` ngay S6; S0 bump cả
  `requirements.txt` + `pyproject.toml` + verify `python -c "import websockets.sync.client"`),
  riêng RSA-sign viết bằng **stdlib** (`hashlib`+`pow`), port từ `crypto.py` của SDK.
- Cấm sửa hành vi KBS/VCI/TCBS/DNSE; cấm log secret; cấm live-test trong CI.
- Endpoint `POST /api/v3/data/ohlc/download` — SDK để `NotImplementedError` →
  implement `raise NotImplementedError` tương đương, ghi rõ trong docs.

## 1. Đặc tả wire-protocol SSI FastConnect v3
> Mức tin cậy: **đã đối chiếu 2 nguồn độc lập** (`ssi-sdk-python` main +
> `ssi-sdk-go` v3.2.0: `stream/enum.go`, `stream/client.go` — khớp channels, frame,
> topics, wildcard `"*"`, parse rules). **Chưa live-confirm**: price ép `str`,
> nanoid length 20, pending 202/code 401114, OTP flows, WS URL, `From/To` hoa —
> tất cả nằm trong checklist live S8 (§6-S8), cấm coi là đúng cho tới khi tick.

### 1.1. Base URLs & conventions

- REST: `https://api.ssi.com.vn` (override qua env). WS: `wss://stream.ssi.com.vn/ws/v3`
  (lưu ý README SDK ghi URL khác — **lấy constant làm chuẩn**).
- Auth thường: header `Authorization: Bearer <access_token>`.
- Lệnh write (place/modify/cancel order + FCO place/cancel): body JSON **raw bytes**,
  ký RSA → header `X-Signature: <hex>`. Xem §1.4.
- Read khác (balance/positions/orders/PPMMR/FCO query/market data): Bearer thuần, không ký.
- Lỗi: 401/403 → auth error; 429 (+`Retry-After`) → rate-limit; ≥400 khác → API error
  (giữ `response_body`). Map sang `BrokerError/*` theo chuẩn repo.
- Date formats: OHLC/summary/orders/FCO-list dùng `"YYYY/MM/DD"`;
  FCO place dùng `"YYYY/MM/DD HH:MM:SS"`. Không tự convert ngầm — validate fail-sớm.

### 1.2. Bảng kiểm endpoint (20 paths: 19 implement + 1 NotImplemented — TOÀN BỘ)

> Cột `clientId`: chỉ balance/positions cần `clientId` (+`accountNo?`); orderBook,
> maxBuySell, FCO list/orderbook KHÔNG dùng `clientId` (đối chiếu `models/*.py` py SDK).

| # | Method | Path | Wrapper vnbroker | Ghi chú wire |
|---|---|---|---|---|
| 1 | POST | `/api/v3/auth/token` | `auth.authenticate` | body `{apiKey, apiSecret, otp?\|transactionId?}` (loại trừ nhau); market-data-only: gọi **không** otp; resp `data?` → `{accessToken, tokenType, expiresAt(epoch s), refreshToken, refreshExpiresAt}` |
| 2 | POST | `/api/v3/auth/refresh` | `auth.refresh` | body `{refreshToken}` |
| 3 | POST | `/api/v3/auth/requestOtp` | `auth.request_otp` | body `{apiKey, apiSecret}`; server tự chọn SMS/email vs Smart-push; trả `transactionId` |
| 4 | GET | `/api/v3/data/ohlc` | `market.get_ohlc` | query `{symbol, from, to, timeFrame(1m/3m/5m/15m/1h/1d/1w/1M), pageIndex(1-based), pageSize}`; intraday default from/to = hôm nay; resp `data[]` → `{symbol, tradingDate, open, high, low, close, volume, value}` |
| 5 | GET | `/api/v3/data/indexList` | `market.get_indexes[_by_board]` | query `{board?}` (HOSE/HNX/UPCOM/DERIVATIVES); resp là **list trực tiếp** |
| 6 | GET | `/api/v3/data/indexSummary` | `market.get_index/board_summary[_historical]` | query `{index?\|board?, tradingDate?}`; lấy phần tử `[0]` hoặc `None` |
| 7 | GET | `/api/v3/data/securitiesByBoard` | `market.get_securities_info[_by_index/_by_board]` | query `{symbol?\|board?\|index?}`; fields: tên VI/EN, `lotSize`, `listedShare`, `icbCode/icbName`, CW (`cwUnderlyingSymbol/cwExercisePrice/cwExecutionRatio`), phái sinh (`openInterest/settlementPrice`, ngày đáo hạn/giao dịch đầu-cuối) |
| 8 | GET | `/api/v3/data/securitiesSummary` | `market.get_securities_summary[_by_index][_historical]` | query `{from, to, symbol?\|index?, pageIndex, pageSize}`; fields: OHLCV + `priceChange(priceChangePercentage)`, `average`, match/deal totals, foreign buy/sell + room |
| 9 | GET | `/api/v3/data/masterdata` | `market.get_master_data[_historical]` | query **`{From, To, pageIndex, pageSize}`** (viết hoa!); tự gom hết pages (`pagesCount`); fields `{board, symbol, tradingDate, ceiling, floor, refPrice}` |
| 9b | GET | `/api/v3/data/ohlc/download` | — (NotImplemented) | SDK gốc để `NotImplementedError`; wrapper `raise NotImplementedError` tương đương + ghi docs. Tính vào audit "100% API" |
| 10 | GET | `/api/v3/account/info` | `account.list_accounts` | không params; resp list `{accountNo, accountType: Cash/Margin/Derivative → EQUITY/EQUITY_MARGIN/DERIVATIVE}` |
| 11 | GET | `/api/v3/trading/accountBalance` | `money.get_balance` / `portfolio` | query `{clientId ✅, accountNo?}`; resp `{equity{…18 fields…}, derivative{…18 fields…}}` |
| 12 | GET | `/api/v3/trading/position` | `portfolio.get_positions` | query `{clientId ✅, accountNo?}`; equity[] `{symbol, quantity, block/dividend/buying/bought/selling/sold, t1/t2SellQuantity, costPrice, mortgage/sellable/restricted}` — **không có market price** (xem map §6-S2); derivative `{derOpenPositions[], derClosePositions[]}` `{long, short, net, bid/askAvgPrice, tradePrice, floating/tradingPL}` |
| 13 | GET | `/api/v3/trading/orderBook` | `portfolio.get_today/historical_orders` | query `{accountNo, from, to, pageIndex, pageSize}` (**không** `clientId`); resp `{accountNo, orderList[], totalRecord}`; order fields `{clientRequestId, orderId, symbol, side(B/S), orderType, price, avgPrice, quantity, osQuantity, filledQuantity, cancelQuantity, orderStatus(PD/WA/RS/SD/QU/FF/PF/FFPC/WM/WC/CL/RJ/EX/IAV), inputTime, modifiedTime, message}` |
| 14 | GET | `/api/v3/trading/ppmmrAccount` | `money.get_ppmmr` | query `{accountNo}`; resp `{equity{…60+ fields: purchasingPower, marginRatio…}, derivative{…SSI/VSDC doubles…}}` → DataFrame giữ toàn bộ cột, không lược |
| 15a | POST/PUT/DELETE | `/api/v3/trading/order` | `equity.place/modify/cancel_order` | **KÝ RSA** (§1.4). Place `{accountNo, symbol, side, quantity, price(str!), orderType, clientRequestId(nanoid 20), deviceId, userAgent}`; price=0 cho MTL/ATO/ATC. Modify: giá HOẶC lượng (cấm đồng thời) + `clientModifyId`. Cancel + `clientCancelId`. Resp `{orderId, clientRequestId, orderStatus}` |
| 15b | GET | `/api/v3/trading/maxBuySell` | `money.get_max_buy_sell[_at_market_price]` | query `{accountNo, symbol(upper), price?(str)}` (**không** `clientId`); resp `{accountNo, maxBuyQty, maxSellQty, marginRatio, purchasePower}` |
| 16a | POST/DELETE | `/api/v3/trading/fco/order` | `fco.place_fco_*` / `cancel_fco` | **KÝ RSA**. 7 loại: `gtd/stop/stop_limit/trailing_stop/trailing_stop_limit/oco/bullbear`; STOP thuần ép `price=MTL, priceSlip=0`; GTD giá Enum → slip=0; OCO có field cứng (`price:"MP", priceSlip:0, stopPrice/activePrice/trailingAmount:0, operator/code:""`); chung `deviceId/userAgent`; cancel `{fcoId}` |
| 16b | GET | `/api/v3/trading/fco/list` | `fco.get_fco_by_*` | query `{accountNo, fcoId?, type?, processStatus(INIT/WAIT/TRI/TRIT/TER/FIS/WC/EXP/ERR), symbol?, side?, from?, to?, pageIndex(1), pageSize(10)}` (**không** `clientId`); `get_fco_by_id` = query + lấy `[0]`/`None` |
| 16c | GET | `/api/v3/trading/fco/orderbook` | `fco.get_fco_order_book` | query `{fcoId, pageIndex(1), pageSize(10)}` |

### 1.3. Auth flows (implement đủ 3 case + market-only)

- Market-data-only: `POST token` **không** otp/transactionId.
- OTP thường/Smart-mã-tay: `otp` thẳng vào `token`.
- Smart push: `requestOtp` → `transactionId` → poll `token` mỗi 5s × 5 lần;
  pending = HTTP 202 + body `{code: 401114}` (chấp nhận cả `status==202`);
  hết lượt → auth error yêu cầu approve lại. `refresh()` khi có refresh token còn hạn.

### 1.4. RSA signing (port duy nhất từ `crypto.py` — stdlib, không dep mới)

- `private_key` = base64 của XML RSA key → lấy `Modulus`, `D` (base64 trong tag).
- Ký chuỗi JSON body (đúng bytes gửi đi): `hex(pow(EM, d, n))` với EM =
  `00‖01‖FF…‖00‖DER(SHA256)‖sha256(body)`. Header `X-Signature`.
- `deviceId` default `"A1:B2:C3:D4:E5:F6"` (cho override qua env),
  `userAgent` = `"vnbroker/<version>"` (không dùng UA của SDK).
- `clientRequestId` nanoid 20 ký tự `[0-9a-zA-Z]` bằng `os.urandom`
  (port `id_generator.py`; vnbroker dùng uuid4 ở facade nhưng wire dùng nanoid —
  **chốt:** sinh nanoid tại transport để đúng định dạng server quen thuộc).

### 1.5. Enums nội bộ (`_enums.py` — giá trị wire giữ nguyên)

`OrderSide BUY="B"/SELL="S"`; `OrderType LO/MTL/MP/ATO/ATC/MOK/MAK/PLO`;
`OrderStatus` 14 mã (§1.2 #13); `Board HOSE/HNX/UPCOM/DERIVATIVES`;
`Timeframe 1m/3m/5m/15m/1h/1d/1w/1M`; `AccountType Cash/Margin/Derivative`;
`FCOType gtd/stop/stop_limit/trailing_stop/trailing_stop_limit/oco/bullbear`;
`FCOOperator greater/greater_or_equal/lesser/lesser_or_equal/equal`;
`FCOStatus` 9 mã. Facade nhận `"BUY"/"SELL"` (chuẩn `brokerage/base.py`) rồi map.

### 1.6. WebSocket protocol (native bằng `websockets`, sync qua thread — không thêm dep)

- Connect `wss://stream.ssi.com.vn/ws/v3` + header `Authorization: Bearer <token>`
  (set sau auth, trước connect); retry backoff theo config.
- Frame JSON: gửi `{method: subscribe|unsubscribe|ping_pong|list_subscription,
  channel: DATA|HEARTBEAT|TRADING, topics: [...]}`; nhận dispatch theo `channel`.
- Topics: DATA `trade.|quote.|room.|put.|oddlot.<SYM>` + `trade.<SYM>@<1m…>`;
  board/index = dùng giá trị board/index như symbol; TRADING `order.<acct|"*" hay>`
  và `portfolio.<acct|"*" hay>` (`"*"` = mọi tài khoản; Go SDK tự set `"*"` khi rỗng —
  đã xác minh `stream/client.go`).
- **Không tồn tại topic FCO riêng**: Go SDK `SubscribeFcoOrderStatus` chỉ là alias của
  `SubscribeOrderStatus` (cùng topic `order.*`, phân biệt bằng `eventType=="fcoEvent"`).
  Wrapper cung cấp alias `subscribe_fco_order_status(account_no)` trỏ cùng topic + ghi rõ
  trong docstring để tránh ngộ nhận. Thêm passthrough `list_subscription`
  (method có trong enum nhưng py README không liệt kê) cho đủ parity WS.
- Parse key rút gọn: trade `{t,s,p,q,si,v→U nếu rỗng}`; interval `{st,t,s,o,h,l,c,v}`;
  quote/oddlot `{t,s,bids/asks[[p,v]…]}`; room `{t,s,tr,cr,bq,bv,sq,sv}`;
  put `{t,s,p,q,tq,tv}`; market `{market,status,tradingDate}`;
  order-update camelCase (lưu ý `osQty/filledQty/cancelQty/inputTime/modifiedTime/rejectReason`,
  `eventType=="fcoEvent"` → FCO update `{fcoId,processStatus,…}`);
  portfolio `{accountNo,totalAsset,cashBalance,stockValue}`.
- Callback gán **trước** connect (enforce, else validation error);
  `wait(timeout)` bắt buộc timeout; ping loop có cancel.

## 2. Kiến trúc native trong vnbroker

```
vnbroker/broker/ssi/
  __init__.py      exports + lazy (không import requests ở top-level ngoài cần thiết)
  _transport.py    SSIHttpClient(requests.Session, Bearer, rate-limit 10rps native,
                   tenacity retry, map lỗi → BrokerError/*) — KHÔNG dùng core/utils/client
  _signing.py      RSA-sign stdlib + nanoid (port §1.4)
  _enums.py        Enums wire (§1.5)
  _paths.py        20 endpoint paths (§1.2: 19 implement + 1 NotImplemented) — hằng số duy nhất chứa URL
  auth.py          SSIAuthService(config, session): authenticate/request_otp/refresh/
                   ensure_authenticated/is_token_valid/revoke (+set_token thủ công)
  account.py       list_accounts
  money.py         get_balance(deriv), get_ppmmr(deriv), get_max_buy_sell[_at_market_price]
  equity.py        get_today? (không — orders thuộc portfolio) → place/modify/cancel
                   (+alias limit/market/ato/atc) @write_gate
  derivatives.py   read phái sinh qua money/portfolio chung (không tách endpoint riêng —
                   SSI gộp trong balance/positions/ppmmr)
  portfolio.py     get_equity/derivative_positions(+open/closed), get_today/historical_orders,
                   portfolio_snapshot (holdings+balance → TCBSPortfolioEngine nếu khớp schema)
  market.py        get_ohlc gom 13 biến thể, indexes/summaries, securities info/summary,
                   master_data (tự gom pages)
  fco.py           7 place + cancel + 5 query + order_book @write_gate cho write
  stream.py        SSIStreamManager (lifecycle, sub/unsub đối xứng + alias
                   subscribe_fco_order_status + list_subscription passthrough,
                   3 callbacks, map message → dataclass nội bộ)
  client.py        SSIBrokerClient(BaseBrokerClient) facade §4.2 + session/enable_write/repr
  exceptions.py    re-export broker.exceptions
```

## 3. Allowlist clone-if-necessary (ngoài danh sách này = tự viết)

| Được port (viết lại, không copy nguyên file) | Nguồn | Ghi chú |
|---|---|---|
| RSA-sign + parse XML key + nanoid | `utils/crypto.py`, `utils/id_generator.py` | Thuần toán, không dính dáng SDK runtime |
| Endpoint paths (20) | `constant.py` | Facts, vào `_paths.py` |
| Payload camelCase schemas + rule ép giá trị (STOP→MTL, OCO hardcode…) | `models/*.py`, `services/trading.py` | Vào service tương ứng, dạng `_PAYLOAD` builders |
| WS topics/message key maps + 202/401114 pending | `services/streaming.py`, `models/streaming.py`, `constant.py` | Vào `stream.py` |
| Quy tắc validate (non-empty/positive/mutual-exclusion) | `utils/validator.py` | Map sang `BrokerValidationError` của repo |
| **Cấm port**: `httpx` transport, retry/rate-limiter custom, dataclass models nguyên trạng, facade Auth/Data/Trading/Stream, `userAgent/deviceId` của SDK | — | Thay bằng `requests`/`tenacity`/pandas/`BrokerSession`/UA vnbroker |

## 4. Quy ước in/out thống nhất với TCBS/DNSE (giữ từ bản trước + bổ sung)

### 4.1. Env (`.env.example`)

```
VNBROKER_BROKER_SSI_CLIENT_ID / _API_KEY / _API_SECRET / _PRIVATE_KEY
VNBROKER_BROKER_SSI_API_URL (default https://api.ssi.com.vn)
VNBROKER_BROKER_SSI_STREAM_URL (default wss://stream.ssi.com.vn/ws/v3)
VNBROKER_BROKER_SSI_DEVICE_ID (default A1:B2:C3:D4:E5:F6)
VNBROKER_BROKER_SSI_ACCOUNT_NO | VNBROKER_BROKER_SSI_TIMEOUT_SECONDS (60.0)
VNBROKER_BROKER_SSI_RATE_LIMIT_RPS (10) | _MAX_RETRIES (5)
```
> Namespace router riêng (không thuộc `VNBROKER_BROKER_SSI_*`, dùng ở P2):
> `VNBROKER_SSI_AUTO_ENABLE` (default 0 — 1 mới cho SSI vào AUTO pool khi creds đủ).

### 4.2. Facade `SSIBrokerClient` (mirror `TCBSBrokerClient`)

`provider_name="SSI"`; `authenticate(otp)->str`; `request_otp/refresh`;
`list_accounts/get_balance/get_derivative_balance/get_holdings/
get_derivative_positions/get_orders/get_order_history/get_purchasing_power/
place|modify|cancel_order(dry_run=True)/place_fco_*(dry_run)/cancel_fco/get_fco_*/
get_ohlc/get_index*/get_securities*/get_master_data/stream_*/portfolio_snapshot`;
`get_account_list/get_account_balance/close/is_authenticated/__repr__`
đúng `BaseBrokerClient` + **`enable_write()` ở facade** (mirror TCBS:
`BaseBrokerClient` không định nghĩa `enable_write` — cả TCBS và SSI đều thêm ở
facade, delegate `session.enable_write()`). DataFrame snake_case (`Int64/float64/category`),
giá VND giữ nguyên (ghi docstring), `raw=True` → dict/list gốc.

## 5. Lộ trình SSI thành nguồn chính của vnbroker

- **P0 (bản này, S0–S8):** broker lane SSI đầy đủ — giao dịch + danh mục + market data
  có auth. Xong P0: SSI thay TCBS cho mọi nhu cầu brokerage (so sánh: TCBS thiếu
  FCO 7 loại/WS đầy đủ; SSI hơn ở OHLC đa timeframe + master data + streaming chuẩn).
- **P1 — `explorer/ssi/` (market-data public, auth không OTP):**
  `quote.history/intraday(+timeframe 1m–1M)/price_depth` (từ OHLC + securities summary;
  depth không có native → NotImplementedError rõ ràng),
  `listing.all_symbols/symbols_by_exchange/symbols_by_group`
  (từ securities info by board/index + master data),
  `trading.price_board` (từ securities summary by index). Đăng ký `ProviderRegistry`,
  `"SSI"` vào `SUPPORTED_SOURCES` của Quote/Listing/Trading.
- **P2 — `source_router` primary pools (QUYẾT ĐỊNH ĐÃ CHỐT — conditional candidate):**
  `core/source_router.py:21` quy định "Open providers only. Do not include providers
  that require auth/token" — SSI (cần apiKey/apiSecret) **không được thêm thẳng** vào
  `OPEN_SOURCE_CANDIDATES`. Thay vào đó: SSI là **conditional candidate**, chỉ xuất hiện
  trong AUTO pool `quote/trading/listing` khi **đồng thời**
  (a) `SSICredentialConfig.from_env()` resolve thành công và
  (b) `VNBROKER_SSI_AUTO_ENABLE=1` (opt-in tường minh, default 0 — AUTO mặc định giữ
  nguyên hành vi open-only). Triển khai trong `get_auto_candidates()` + test cả 4 trạng thái
  (thiếu creds / thiếu flag / đủ cả hai / revoke giữa chừng).
  Chưa đủ để thành primary: `build_source_order` lọc primary qua `PRIMARY_SOURCE_POOLS`
  (`quote=["vci"]`, `trading=["kbs"]`) và `_get_trading_primary_override`
  (`source_router.py:50`) hiện chỉ nhận `{kbs, vci}` — P2 **bắt buộc** sửa cả hai:
  (i) khi SSI conditional-active thì chèn `"ssi"` vào đầu pool `quote/trading/listing`
  tương ứng, (ii) mở override chấp nhận `"ssi"`
  (vd `vnbroker_TRADING_AUTO_PRIMARY=ssi`), (iii) giữ nguyên pool khi flag/creds thiếu.
  Test: thứ tự `build_source_order` có/không SSI + override hợp lệ/không hợp lệ.
  **TRUNG THỰC KỸ THUẬT:** SSI không có Company fundamentals/Finance/News →
  Company/Finance/News giữ KBS/VCI primary, SSI không tham gia các module này
  (ghi rõ trong docs, cấm fake-fallback trả rỗng).
- **P3 — Cutover default:** parity-test SSI vs KBS/VCI (SMA giá đóng ±sai số làm tròn,
  symbol coverage từ master data), reliability 30 ngày (uptime/429-rate),
  rồi mới `DEFAULT_SOURCE="SSI"` cho Quote/Trading/Listing sau approve riêng.
- **Bảng phủ module (đích cuối):**

| Module | SSI native | Nguồn còn lại |
|---|---|---|
| Quote/Trading/Listing | ✅ primary (P1–P3) | KBS/VCI fallback |
| Brokerage (account/orders/FCO/stream) | ✅ duy nhất full FCO+WS | TCBS/DNSE song song |
| Company/Finance/News/Fund | ❌ SSI không có | KBS/VCI/FMarket/RSS giữ nguyên |

## 6. Slices thực hiện (DAG: S0 → S1 → S2 → S3 → S4 → S5/S6 song song → S7 → S8)

- **S0 — Nền + transport + signing + enums + fixtures:**
  `_paths/_transport/_signing/_enums`, `SSICredentialConfig`,
  `exceptions.py`, bump `websockets>=12.0` (`requirements.txt` + `pyproject.toml`;
  verify `python -c "import websockets.sync.client"`),
  `tests/unit/broker/ssi/conftest.py` (mock `requests.Session`
  + WS giả — **không cài thêm gì**), fixtures JSON. Nghiệm thu: import xanh;
  test vector RSA (ký 1 payload mẫu → verify bằng key công khai tương ứng trong test);
  nanoid đúng alphabet/length; quét fixture không secret thật.
- **S1 — Auth:** đủ 3 case + market-only + poll pending 202/401114; token vào
  `BrokerSession(provider="SSI")` (expiresAt epoch → datetime); caplog không secret.
  ≥12 cases, coverage ≥85% (chuẩn thống nhất toàn plan — xem S8).
- **S2 — Account/Portfolio read:** `list_accounts`, balance equity/derivative (giữ
  đủ fields, không lược PPMMR), positions (equity + open/closed deriv), today/history
  orders (`totalRecord`), PPMMR full-columns. Golden snapshot fixtures. Coverage ≥85%.
  `portfolio_snapshot` map tường minh (cấm silent no-op — `holdings_snapshot` của
  `TCBSPortfolioEngine` trả rỗng khi thiếu cột, đã xác minh `broker/tcbs/portfolio.py:51`):
  `symbol←symbol`, `quantity←quantity`, `average_cost←cost_price`,
  `market_price←enrich từ securities summary close_price cùng ngày` (thiếu → cột NaN +
  `logger.warning` + ghi rõ trong output, không trả rỗng lặng lẽ).
- **S3 — Equity write:** validate trước gate; dry_run chặn (mock session không gọi);
  `enable_write` bắt buộc khi thực; price ép `str` trên wire; modify cấm giá+lượng
  cùng lúc; idempotency nanoid. Mirror `test_order_write_flow.py` TCBS.
- **S4 — FCO:** 7 place (rule ép STOP/OCO/GTD §1.2-16a) + cancel + 5 query + order_book;
  date format fail-sớm; ≥20 cases + case "GTD rồi hủy ngay" trên mock; coverage ≥85%.
- **S5 — Market:** `get_ohlc` gom 13 biến thể (timeframe map, intraday default today,
  historical require from/to); index/board summary `[0]/None`; securities info/summary;
  master data gom pages (`pagesCount`); download → NotImplementedError.
- **S6 — Stream:** native WS (§1.6): connect Bearer + retry; sub/unsub đối xứng +
  alias `subscribe_fco_order_status` (cùng topic `order.*`, docstring ghi rõ alias —
  đã xác minh `ssi-sdk-go/stream/client.go`) + `list_subscription` passthrough;
  callbacks trước connect; parse đủ 10 message types; `wait(timeout)`; ping loop cancel.
  Test trên WS giả (không socket thật), `pytest --timeout=30` không treo; coverage ≥85%.
- **S7 — Facade + Registry + docs:** `client.py` full §4.2; auto-register `ssi`;
  `broker(provider="ssi")`; `.env.example`; `docs/SSI_USAGE_GUIDE.md`
  (3 snippet: market-only không OTP / auth+read / FCO an toàn) + test snippet trên mock;
  compliance test mirror TCBS (provider/authenticate/balance/close/repr).
- **S8 — Audit + live gate + release:** `tests/integration/broker/test_ssi_live.py`
  gated env (`manual`: auth OTP, balance, GTD-hủy-ngay); DoD: full unit xanh
  0 failure (≥522 baseline + mới), `mypy --strict`, `ruff` clean, coverage SSI ≥85%,
  `artifacts/ssi-handover/` 6 file; CHANGELOG/README/CLAUDE.md + bump minor.
  Checklist live-confirm bắt buộc (từng quirk §1 chỉ được coi là đúng sau khi tick):
  WS URL thực tế, price ép `str` trên wire, nanoid length-20 được server chấp nhận,
  pending 202/code 401114, cả 3 OTP flows, `From/To` hoa ở masterdata, wildcard `"*"`
  cho order/portfolio subscribe, (8) `clientId` chỉ gửi ở balance/positions —
  orderBook/maxBuySell/FCO-list không gửi (khớp §1.2).

## 7. Rủi ro & giả định

1. Site docs SSI 403 từ mạng hiện tại → đặc tả §1 lấy từ source công khai của SDK;
   S8 live-test đối chiếu lại, lệch thì sửa plan trước khi release.
2. README SDK vs constant lệch WS URL → lấy `wss://stream.ssi.com.vn/ws/v3`, verify ở S6-live.
3. `private_key` (base64 XML RSA) = secret cấp cao nhất: env-only, không fixture thật.
4. SDK Alpha → API server có thể đổi: `_paths.py` tập trung mọi path để đổi 1 chỗ;
   test vector RSA + golden fixtures bắt regression.
5. OTP/Smart-OTP cần người + thiết bị → live bán tự động, không CI.
6. Mọi thay đổi hành vi lane khác = regression → fail S8.
7. Audit độc lập (2026-09-22) đã đối chiếu plan với repo + `ssi-sdk-go` v3.2.0:
   xác nhận WS URL/rate-limit/wildcard/channels/frame/market-only-auth/RSA-stdlib;
   phát hiện và đã sửa trong bản này: pin `websockets>=12.0`, đếm endpoint 20
   (19 + 1 N/I), SSI conditional trong AUTO pool, map `portfolio_snapshot` tường minh,
   `enable_write` ở facade, coverage thống nhất ≥85%.
   Đính chính 1 điểm audit sai: **không tồn tại topic FCO riêng** —
   `SubscribeFcoOrderStatus` trong `ssi-sdk-go/stream/client.go` chỉ là alias của
   `SubscribeOrderStatus` (cùng topic `order.*`); plan giữ parse `fcoEvent` + alias wrapper.

## 8. Lệnh verify chuẩn

```bash
python -c "import websockets.sync.client; print('ws-sync OK')"  # S0: pin >=12.0
pytest tests/unit/broker/ssi -v
pytest tests/unit -v
mypy vnbroker --strict
ruff check vnbroker
ruff format --check vnbroker
pytest tests/unit/broker/ssi --cov=vnbroker/broker/ssi --cov-report=term-missing
vnbroker_RUN_LIVE_INTEGRATION=1 pytest tests/integration/broker/test_ssi_live.py -v  # manual, creds thật
```
