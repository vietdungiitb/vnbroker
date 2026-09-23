# SSI Swap Parity Plan — Dùng SSI qua lại với KBS/VCI + full tính năng riêng SSI

> Mục tiêu: **không thay KBS/VCI bằng SSI**, mà nâng SSI lên mặt bằng có thể **swap qua lại** với KBS/VCI ở các hàm tương đồng (T1/T2), đồng thời dùng đầy đủ tính năng riêng của SSI (T3: trading, FCO, WebSocket, market-native).
> Nguồn: `developers.ssi.com.vn/docs/api-reference` (Overview + auth-token, trade-order-place/orderBook, data-ohlc/securitiesByBoard/securitiesSummary/indexList/indexSummary/masterData, connectWebSocket, subscribeUnsubscribeMarketData, fco-order-place) + code `vnbroker/broker/ssi/*`, `vnbroker/explorer/ssi/*`, `vnbroker/base.py`, `vnbroker/common/data.py`, `vnbroker/core/source_router.py`.
> Ngày: 2026-09-23. Trạng thái: P0 DONE, P1+P2+P3 DONE (2026-09-23) — xem §5.
> Phát hiện thêm khi làm P3: deadlock cold-start `_health_lock` (`Lock` → `RLock`,
> `core/source_router.py`) — test AUTO mới là trigger đầu tiên trên process tươi.

## 1. Khung 3 tầng

| Tầng | Định nghĩa | Ví dụ | Chiến lược |
|---|---|---|---|
| T1 — Swappable | Trùng tên, trùng ý nghĩa ở cả SSI/KBS/VCI | `quote.history`, `listing.all_symbols/by_exchange/by_group`, `trading.price_board` | Chuẩn hóa signature + schema + error → đổi `source=` là chạy |
| T2 — SSI-enhanced | Trùng tên nhưng SSI giàu hơn | `listing.symbols_by_industries` (native `icb_code/name`), `history` daily từ IPO + intraday 1y, `securitiesSummary` (foreign/room/deal), `masterdata` (ceiling/floor/ref), `indexList/Summary` | Giữ cột chung + thêm cột `ssi_*`, không drop thông tin |
| T3 — SSI-only | Chỉ SSI có | Trading `place/modify/cancel`, `orderBook/position/balance/maxBuySell/ppmmr`, FCO 7 loại (TS/PRO/ST/TPRO/BB/OCO/MA), WS `trade/quote/room/put/oddlot/market`, `orderEvent/orderMatch/portfolio/fcoEvent` | Không ép vào `StockComponents`; expose qua `vn.broker(provider='ssi')` + `explorer.ssi` trực tiếp |

Quy ước sử dụng:

```python
from vnbroker import Vnbroker
vn = Vnbroker()

# T1/T2: swap qua lại — cùng tên hàm, cùng cột chung
vn.stock("ACB", source="SSI").quote.history(start="2024-01-01", end="2024-12-31", interval="1D")
vn.stock("ACB", source="KBS").quote.history(start="2024-01-01", end="2024-12-31", interval="1D")
vn.stock("ACB", source="VCI").quote.history(start="2024-01-01", end="2024-12-31", interval="1D")

# T3: tính năng riêng SSI — không có ở KBS/VCI
client = vn.broker(provider="ssi", api_key="...", api_secret="...")
client.authenticate()                    # data-only, không OTP
client.authenticate(otp="...")           # full trading
client.get_ohlc("SSI", timeframe="1d")   # broker lane market
client.place_limit_order(...)            # dry_run=True mặc định
```

## 2. Đặc tả SSI liên quan (tóm tắt)

| Nhóm | Endpoint | Ghi chú dùng cho parity |
|---|---|---|
| Auth | `POST /api/v3/auth/token` (`apiKey/apiSecret`, OTP optional; data-only không OTP), `/auth/refresh`, `/auth/requestOtp` | Market lane dùng data-only; trading mới cần OTP + RSA `X-Signature` |
| Market REST | `GET /data/ohlc?symbol&from&to&timeFrame=1m/3m/5m/15m/30m/1h/1d&pageIndex&pageSize` — intraday 1y, daily từ IPO; `from/to`: daily `YYYY/MM/DD`, intraday `YYYY/MM/DD HH:mm:ss` | Core của T1/T2 quote |
| Market REST | `GET /data/securitiesByBoard?symbol\|board(HOSE/HNX/UPCOM)\|index` (chỉ 1 filter); fields `symbol/symbolNameVi/En/board/lotSize/maturityDate/firstTradingDate/cwUnderlying/cwExercisePrice/listedShare/icbCode/icbName/openInterest/settlementPrice` | Core listing + ICB + lọc CW/bond/futures client-side |
| Market REST | `GET /data/securitiesSummary?symbol\|index&from&to(YYYY/MM/DD)` — `open/high/low/close/average/priceChange/totalMatch/totalBuy/totalSell/totalForeignBuy/Sell/remainForeignRoom/totalDeal/openInterest/settlementPrice` | Enrich board + phân tích room ngoại |
| Market REST | `GET /data/indexList?board`, `GET /data/indexSummary?board\|index&tradingDate` | Module indices mới |
| Market REST | `GET /data/masterdata?from&to` — `{symbol,exchange,tradingDate,ceiling,floor,refPrice}` | Board ref prices |
| WS Market `wss://stream.ssi.com.vn` | channel `DATA`, topics `trade/quote/room/put/oddlot/market.[symbol-symbol\|index\|exchange\|*]@[tick/1m/5m]` (market không interval); `trade={s,t,p,q,a,si,o,h,l,v}`, `quote={s,t,bids,asks}`, `room={tr,cr,bq,bv,sq,sv}`, `market={s,b,t,ce,fl,ref}` + flag `ATO/LO/ATC` | Bù `intraday` tick + `price_depth` realtime (REST không có) |
| Trading REST | `POST /trading/order` (`clientRequestId/accountNo/symbol/side B\|S/orderType LO\|ATO\|ATC\|MP/qty/price/deviceId` + `X-Signature`), `PUT/DELETE order`, `GET orderBook?accountNo&from&to(ISO8601)`, `position/maxbuysell/accountBalance/ppmmrAccount/account-info` | T3, broker lane đã có |
| FCO | `POST /trading/fco/order` + `DELETE`, `GET fco/list/orderbook/statusHistory` | T3, broker lane đã có cơ bản |
| WS Trading + WS API (beta) | `orderEvent/orderMatchEvent/clientPortfolioEvent/fcoEvent`; `tradingws: order.place/amend/cancel, fco.place, query.position` (max 10 conn/key) | Phase sau |

## 3. Hiện trạng và điểm nghẽn swapping

### 3.1 Ma trận coverage hiện tại

| Yêu cầu | SSI hiện tại | KBS/VCI |
|---|---|---|
| `quote.history` | `explorer/ssi/quote.py`: chặn `30m` (`:119`), chỉ `YYYY-MM-DD→YYYY/MM/DD`, `get_all=False` cắt 1000, `1w/1M` vượt doc | Đủ `1m→1M`, resample client (VCI), suffix map (KBS) |
| `quote.intraday` | luôn `NotImplemented` (`:249`) | Tick phiên hiện tại ✅ |
| `quote.price_depth` | luôn `NotImplemented` (`:253`) | VCI ✅, KBS ❌ |
| `listing` | `all_symbols/by_exchange/by_group/by_industries/industries_icb` ✅; `warrant/bond/futures/gov` raise (`listing.py:178`) | Full hơn |
| `trading.price_board` | 17 cột, không bid/ask, cố định today (`trading.py:97-120`), sequential N+1 | Có bid/ask (VCI), batch tốt hơn |
| `company/finance/news` | toàn rỗng (SSI không có endpoint) | ✅ |
| `indices/screener` | broker có (`market.py:get_indexes/get_index_summary`) nhưng explorer chưa expose | Có ở KBS/VCI |

### 3.2 Blockers (từ code thật)

1. **Signature lệch** — `SSIQuote.history(...)` thiếu `show_log/parallel/symbols/max_concurrency`; `BaseAdapter._invoke_provider_method (base.py:134)` filter lặng lẽ theo signature → param bị drop không báo.
2. **Schema lệch** — board SSI 17 cột không bid/ask (`explorer/ssi/trading.py:24`); `history` thêm `value` chỉ khi `get_all=True`.
3. **Semantic lệch** — SSI chặn `30m`, mất `HH:mm:ss`; KBS/VCI resample client.
4. **Auth lệch** — SSI đòi key ngay cả module rỗng (`company/financial/news.__init__` raise); `SSIBrokerClient (broker/ssi/client.py:69)` thì không raise ở construct.
5. **Error lệch** — SSI rỗng câm vs `NotImplemented`; `_call_with_fallback (common/data.py:250)` chỉ fallback empty + `NotImplemented`, lỗi mạng primary thì raise ngay.
6. **Router loại SSI** — `source_router.OPEN_CANDIDATES` chỉ `vci/kbs` → `AUTO` không qua SSI.
7. **SSI-only chưa lộ facade** — `SSIMarketService/Equity/FCO/Money/Portfolio/Stream` đã có nhưng explorer chỉ wrap 3/6 module.

## 4. Kiến trúc mục tiêu

```
vn.stock("ACB", source="SSI"|"KBS"|"VCI")     # T1/T2 swappable
  → StockComponents → Company/Finance/... (BaseComponent._call_with_fallback)
    → ProviderRegistry.get(module, source)
      → explorer/ssi|kbs|vci/* (canonical kwargs + normalized schema)

vn.broker(provider="ssi")                      # T3 SSI-only
  → SSIBrokerClient (.market/.equity/.fco/.money/.account/.portfolio/.stream)
vn.ssi_extra / explorer.ssi trực tiếp          # T2 nâng cao
```

* **Canonical kwargs:** `history(start,end,interval,count_back,length,get_all,floating,to_df)`; mỗi explorer tự translate (SSI: `YYYY/MM/DD[ HH:mm:ss]` + `timeFrame`; KBS: `DD-MM-YYYY` + suffix; VCI: `countBack`). Drop param phải `warning`, không câm.
* **Normalized schema + `ssi_*`:** board chung `[symbol,time,exchange,ceiling,floor,ref,open,high,low,close,average,volume,total_value,price_change,pct,foreign_buy,foreign_sell]` + cột `ssi_*` khi có; `history` chung `[time,open,high,low,close,volume]` + optional `value`.
* **Capability manifest** (`explorer/ssi/capabilities.py` mới): `{module.method: supported|enhanced|only|unsupported}` để facade fallback hay raise rõ thay vì DF rỗng.
* **Auth 2 chế độ:** `data_only` (lazy, không OTP) cho market; `trading` (OTP + RSA) cho write. Module T1/T2 cho init không key → fallback êm (warn thay vì raise).
* **AUTO v2 credential-aware:** `build_source_order(module)` luôn có `vci/kbs` + thêm `ssi` khi có key; primary default vẫn KBS/VCI (tránh quota 10rps), SSI là failover + opt-in primary qua `vnbroker_SSI_AUTO_PRIMARY=1`.

## 5. Kế hoạch phase

### P0 — Swap được T1 ✅ DONE (W1–W5)
- [x] W1 — `30m` end-to-end (không chỉ `quote.py`): thêm `MINUTE_30 = "30m"` vào `Timeframe` (`broker/ssi/_enums.py:56` — hiện chỉ có `1m/3m/5m/15m/1h/1d/1w/1M`); bỏ raise `explorer/ssi/quote.py:119`; sửa message lỗi `quote.py:127` và `market.py:170` (hiện liệt kê thiếu `30m` ở market / thừa `30m` ở quote — mâu thuẫn nhau).
- [x] W5 — `HH:mm:ss` end-to-end (không chỉ quote): `explorer/ssi/quote.py:_validate_date` nhận `YYYY-MM-DD[ HH:mm:ss]`; `broker/ssi/market.py:get_ohlc (:175-176)` và `get_securities_summary (:414-415)` chuyển từ `validate_ssi_date` (date-only, `_utils.py:62`) sang chấp nhận datetime (đã có sẵn `validate_ssi_datetime`, `_utils.py:76` — dùng cho FCO); loop `pagesCount/itemsCount`; thống nhất `floating/count_back/length`.
- [x] W4 — lazy-auth cho module rỗng (điều kiện nghiệm thu "đổi source không vỡ"): `explorer/ssi/company.py:170`, `financial.py:56`, `news.py:61` chuyển `resolve_credentials(...)` ở `__init__` sang lazy ở lần gọi mạng đầu (warn thay vì raise khi thiếu key), theo mẫu `SSIBrokerClient.__init__ (broker/ssi/client.py:69)` không raise ở construct. `quote/listing/trading` giữ fail-fast (module thật, cần key).
- [x] W2 — fallback 1 chiều + sửa bug trùng dòng: `common/data.py:580-581` `Trading` định nghĩa `FALLBACK_MAP` 2 lần — dòng 581 override dòng 580 làm SSI fallback thành dead code → xóa dòng 581, giữ `{"DNSE": ["KBS","VCI"], "SSI": ["KBS","VCI"]}`. Giữ **1 chiều SSI→KBS,VCI** (như `Company :643`, `Finance :937` đã có); **không** thêm `KBS→SSI` (user KBS không key sẽ bị lao vào quota 10rps SSI). `Quote :374` và `Listing :489` hiện không có `FALLBACK_MAP` (kế thừa `{}` từ `BaseComponent :204`) — P0 bổ sung cho 2 class này nếu muốn parity đầy đủ, không bắt buộc.
- [x] W3 — mở rộng catch trước khi đổi error type: `BaseComponent._call_with_fallback (common/data.py:276)` hiện chỉ `except (NotImplementedError, AttributeError)` + skip empty-DF; `UnsupportedMethodError (core/exceptions.py:100)` là subclass `ProviderError`, **không** lọt catch → primary SSI sẽ raise ngay (`:279-283`) thay vì fallback. Vì vậy trước khi áp §6 ("raise thay vì rỗng"), phải thêm `UnsupportedMethodError` (hoặc `ProviderError`) vào tuple catch — nếu không, giữ nguyên empty-DF.
- [x] `explorer/ssi/listing.py`: alias `exchange` (`HOSE/HNX/UPCOM`), test parity `[symbol,organ_name]`.
- [x] `explorer/ssi/trading.py`: `price_board(symbols_list, trading_date?=today)` + batch concurrent (8) + `source_used=SSI`; document không bid/ask.
- [x] Annotate `source_used/source_requested` trên mọi fallback.
- [x] Test (đúng cấu trúc hiện có `tests/unit/explorer/ssi/`, không phải `tests/unit/ssi/`): `tests/unit/explorer/ssi/test_swap_parity.py` — `test_swap_history_ssi_kbs_vci`, `test_swap_listing`, `test_swap_board` (mock service, assert schema chung) + regression cho W1–W5 (`30m` đi qua enum, datetime qua `get_ohlc`, lazy-auth không key, fallback `UnsupportedMethodError`, không còn duplicate `FALLBACK_MAP`).
- Nghiệm thu: đổi `source` SSI↔KBS↔VCI cho 3 hàm trên không vỡ caller **kể cả khi chưa có SSI key** (nhờ W4) và lỗi unsupported vẫn fallback (nhờ W3).

### P1 — T2 SSI-enhanced ✅ DONE
- [x] Mới `explorer/ssi/indices.py` (`SSIIndices`, registry `indices/ssi`): `index_list(board?, TTL 6h)`, `index_members(index)` (securitiesByBoard), `index_summary(index|board, trading_date?, TTL 5m)`, `index_history(index, start, end)` (bulk securitiesSummary, không N+1).
- [x] Mới `explorer/ssi/securities.py` (`SSISecurities`, registry `securities/ssi`): `summary(symbol|index, start, end)`, `master(trading_date?, TTL 60s)`, `foreign_room(...)` (subset cột foreign/room).
- [x] Mới `explorer/ssi/screener.py` (`SSIScreener`, registry `screener/ssi`): `stock(params, limit)` lọc local (`exchangeName/indexName/icb/min_listed_shares`); lọc thanh khoản (`min_total_match[_value]`) bắt buộc `indexName` (bulk summary), nếu không raise hướng dẫn dùng KBS/VCI.
- [x] Cache TTL phân tầng: `all_symbols` 6h (`listing.py`), `index_list` 6h, `index_summary` 5m, `master` 60s.
- Nghiệm thu: cột `ssi_*` tồn tại khi `source=SSI`; screener cơ bản chạy.

### P2 — T3 SSI-only full ✅ DONE (market-data scope)
- [x] `SSIExplorerSession.stream_manager()` (`explorer/ssi/_auth.py`) — WS manager bound sẵn token.
- [x] Mới `explorer/ssi/live.py` (`SSILive`, registry `live/ssi`, `_stream_factory` inject cho test): `intraday_ticks(symbol, timeout)` (WS `trade.*` → `[time,price,volume,side]`), `depth_snapshot(symbol, timeout)` (WS `quote.*` → `[side,price,volume]` BID/ASK), `session_snapshot(symbols, trading_date?)` (REST masterdata → `[symbol,board,trading_date,ceiling,floor,ref]`, không cần WS).
- [x] Trading/FCO/WS order giữ ở `vn.broker(provider='ssi')` (đã có, không đụng).
- Nghiệm thu: tick/depth có dữ liệu trong giờ giao dịch (live-gated, chưa chạy ở đây); unit dùng stream double.
- Ghi nhận: `market.*` topic (cờ phiên ATO/LO/ATC) chưa có subscribe trong `SSIStreamManager` — follow-up nếu cần.

### P3 — AUTO + chịu tải ✅ DONE (scope P0 của phase)
- [x] `core/source_router.py`: `SSI_AUTO_CANDIDATES` (quote/listing/trading — loại company/financial/news vì rỗng sẽ false-success), `has_ssi_credentials()` (env, không network), `get_auto_candidates` append `ssi` khi có key (failover cuối), opt-in primary qua `vnbroker_SSI_AUTO_PRIMARY=1` (pattern theo `vnbroker_TRADING_AUTO_PRIMARY`).
- [x] Token-bucket 10rps SSI đã có ở `_transport`; `price_board` concurrent(8) đã làm ở P0.
- [x] **Bug blocking phát hiện bởi test mới**: deadlock cold-start — `build_source_order` giữ `_health_lock` (`threading.Lock`) rồi `_is_in_cooldown → _ensure_store_loaded` đòi cùng lock trên process tươi (treo vĩnh viễn, đã xác minh bằng faulthandler). Fix: `_health_lock = threading.RLock()`. Test AUTO cũ không dính vì store đã load từ test khác trong cùng process.
- Nghiệm thu: kill VCI mock → qua SSI với `source_used=SSI` (covered); SSI cuối order mặc định, đầu order khi opt-in.

## 6. Rủi ro và giới hạn chấp nhận

* SSI không có BCTC/news/officers → không thể main 100%; mô hình đúng là **SSI-first + KBS/VCI-fallback** cho 3 module đó. Mọi unsupported phải raise `UnsupportedMethodError` kèm gợi ý — **nhưng chỉ sau khi đã mở rộng tuple catch ở `_call_with_fallback` (W3)**, nếu không sẽ phá fallback; trong lúc chưa sửa catch thì giữ empty-DF.
* Quota 10rps + `pageSize` default 10 → bắt buộc batch + cache, nếu không chậm hơn scrape KBS/VCI.
* WS `interval` chỉ `tick/1m/5m` (không `3m` như REST), `market.*` không interval — code phải tách đường.
* WS API trade đang beta — chưa production.

## 8. Phase P4 (follow-up) ✅ DONE

| Item | Nội dung | Files |
|---|---|---|
| P4a market.* | `subscribe/unsubscribe_symbol_market_status` (`stream.py`) + `SSILive.session_flags` → `[market,status,trading_date]` | `broker/ssi/stream.py`, `explorer/ssi/live.py` |
| P4b batch | `SSIQuote.fetch_multiple(symbols, start, end, interval, max_concurrency=8)` — ThreadPool, giữ thứ tự, lỗi/cụm lẻ thành empty frame có `attrs[error]`, trả `Dict[symbol, DF]` | `explorer/ssi/quote.py` |
| P4c persist debounce | `_persist_state` flush khi đủ 10 events hoặc quá 1s; `flush_router_state()` cho shutdown/test; `reset_router_state` reset counter | `core/source_router.py` |
| P4d live-gated | `TestSSIP4Live` 7 tests (30m, datetime window, fetch_multiple, indices/securities, screener, session_snapshot, WS tolerant) — chạy với `vnbroker_RUN_LIVE_INTEGRATION=1` + key + giờ giao dịch | `tests/integration/explorer/test_ssi_live.py` |

Ma trận T1/T2/T3 cập nhật (mới so với §1): T2 thêm `indices` (`index_list/members/summary/history`), `securities` (`summary/master/foreign_room`), `screener.stock`; T3 thêm `live` (`intraday_ticks/depth_snapshot/session_snapshot/session_flags`); T1 `price_board` có thêm `trading_date` + concurrent.

* Sửa (thực tế P0–P4): `explorer/ssi/{quote,listing,trading,company,financial,news,_auth,__init__}.py`, `broker/ssi/{_enums,market,stream}.py`, `common/data.py` (W2 trùng dòng + W3 catch + Quote/Listing map), `core/source_router.py` (SSI candidates + opt-in primary + RLock + persist debounce).
* Mới (thực tế): `explorer/ssi/{indices,securities,screener,live}.py`, `tests/unit/explorer/ssi/{test_swap_parity,test_indices_securities,test_screener,test_live}.py`, `tests/unit/core/test_source_router_ssi.py`, `tests/integration/explorer/test_ssi_live.py::TestSSIP4Live` (gated `vnbroker_RUN_LIVE_INTEGRATION=1` + key).
* Không làm (ghi nhận): `capabilities.py` (chưa cần — fallback hiện tại đủ), `quote.fetch_multiple` async thuần (dùng ThreadPool như TCBS), `market.*` subscribe đã làm ở P4a.
* Env opt-in SSI primary: `vnbroker_SSI_AUTO_PRIMARY=1` (pattern theo `vnbroker_TRADING_AUTO_PRIMARY`).
* Lưu ý xác minh live: `1w/1M` có trong `Timeframe` nhưng doc SSI chỉ tới `1d` — cần test live trước khi document.
