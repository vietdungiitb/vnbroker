# DNSE — Market Data WebSocket (tài liệu nhà cung cấp)

**Nguồn:** người dùng cung cấp ngày 2026-10-09 (bản gốc của DNSE).
**Mục đích trong repo:** làm chuẩn đối chiếu cho
`vnbroker/connector/dnse/websocket.py`. Bản sao schema quan sát được từ server thật
nằm ở `dnse_ws_schema_observed.json` cùng thư mục.

> **Cảnh báo đã kiểm chứng bằng thực thi (2026-10-09):** tài liệu này **không khớp 100%**
> với server thật. Xem `dnse_ws_schema_observed.json` và `PM_AUDIT_REPORT_20261009.md` §11.
> Danh sách lệch đã đo ở cuối file.

---

## Thông tin kết nối chung

- Base URL: `wss://ws-openapi.dnse.com.vn`
- SDK chính thức: https://github.com/dnse-tech/openapi-sdk
- Định dạng: `msgpack` (nhanh, tiết kiệm băng thông) hoặc `json` (dễ đọc)
- Mọi mã chứng khoán phải **CHỮ IN HOA**: `ACB`, `HPG`, `41I1G2000`
- Một kết nối có hiệu lực **tối đa 8 giờ**, server chủ động ngắt sau thời gian này
- Cơ chế duy trì kết nối:
  - Server gửi **1 PING sau mỗi 3 phút**
  - Mỗi PING yêu cầu **PONG trong tối đa 1 phút**; quá hạn server ngắt kết nối
  - Client **được phép gửi PONG chủ động** kể cả khi không nhận PING (case: WS lib tự
    handle, mobile NAT cắt idle TCP, miss PING frame)
- **Giới hạn: tối đa 10 connections/user và 200 streams/connection**

| Case | Mô tả | Kết quả |
|---|---|---|
| 1 Good | T+0 Server→PING, T+1 Client→PONG (lặp mỗi 3 phút) | ✅ giữ kết nối |
| 2 Bad | T+0 Server→PING, không PONG, T+1min Server ngắt | ❌ chết |
| 3 Client-initiated | Trong mỗi 3 phút Client→PONG chủ động | ✅ giữ kết nối |

## Kênh dữ liệu

| Kênh (Function) | Mô tả | Loại | Tần suất |
|---|---|---|---|
| Security Definition | Giá trần/sàn, trạng thái mã | Batch (BOD) | 1 lần trước GD (~08:00) |
| Trade | Khớp lệnh thời gian thực | Real-time | khi có thay đổi |
| Trade Extra | Khớp lệnh + mua/bán chủ động, giá TB | Real-time | khi có thay đổi |
| Quotes | Độ sâu thị trường | Real-time | khi có thay đổi |
| OHLC | Nến đang hình thành | Real-time | khi có khớp |
| OHLC Closed | Nến đã đóng | Periodic | khi đóng nến |
| Expected Price | Giá/KL dự kiến ATO/ATC | Real-time | khi có thay đổi |
| Market Index | Chỉ số (VNINDEX, HNX…) | Periodic | chu kỳ 5 giây + tổng hợp cuối ngày |
| Foreign Investor | Giao dịch NĐT nước ngoài | Real-time | khi có thay đổi |
| Estimated VN30 | VN30 dự tính | Real-time | khi có thay đổi |
| Session | Thông tin phiên | Real-time | khi có thay đổi |
| Top cổ phiếu ảnh hưởng chỉ số | Đóng góp điểm số | Real-time | khi có thay đổi |

## Input dùng chung

- **`board_id`**: `G1` lô chẵn · `G3` board PLO · `G4` lô lẻ · `T1` thỏa thuận lô chẵn
  9h-14h45 · `T3` thỏa thuận lô chẵn 14h45-15h · `T4` thỏa thuận lô lẻ 9h-14h45 ·
  `T6` thỏa thuận lô lẻ 14h45-15h
- **`market_index`**: `HNX30` · `VN30` · `HNX` · `VNXALLSHARE` · `UPCOM` · `VNDIVIDEND` ·
  `VNINDEX` · `VN50GROWTH` · `VN100` · `VNMITECH`
- **`tsc_prod_grp_id`**: `FBX` trái phiếu tương lai · `FIO` hợp đồng chỉ số · `HCX` trái
  phiếu DN HNX · `STO` cổ phiếu HOSE · `STX` cổ phiếu HNX · `UPX` cổ phiếu Upcom

## Schema từng kênh

### Security Definition — `security_definition.{board_id}.{encoding}`
Input: `symbols`, `board_id`

```
marketId, boardId, isin, symbol, productGrpId, securityGroupId,
basicPrice, ceilingPrice, floorPrice, openInterestQuantity,
securityStatus, symbolAdminStatusCode, symbolTradingMethodStatusCode,
symbolTradingSanctionStatusCode, listingDate, finalTradeDate,
time { Seconds, Nanos }
```

### Trade — `tick.{board_id}.{encoding}`
Input: `symbols`, `board_id`

```
marketId, boardId, isin, symbol, matchPrice, matchQtty,
totalVolumeTraded, grossTradeAmount, highestPrice, lowestPrice,
openPrice, tradingSessionId, time { Seconds, Nanos }
```

### Trade Extra — `tick_extra.{board_id}.{encoding}`
Thêm so với Trade: `side` (SELL/BUY), `avgPrice`

### Quotes — `top_price.{board_id}.{encoding}`
Input: `symbols`, `board_id` — HOSE hỗ trợ 3 mức giá, HNX/UPCOM 10 mức

```
marketId, boardId, isin, symbol,
bid    : [{ price, quantity }],
offer  : [{ price, quantity }],
totalOfferQtty, totalBidQtty,
time { Seconds, Nanos }
```

### OHLC — `ohlc.{resolution}.{encoding}`
Input: `symbols` (phái sinh truyền `symbolType`, VD `VN30F1M`), `resolution`
(`1, 3, 5, 15, 30, 1H, 1D, 1W`). **Không có `board_id`** — segment là resolution.

```
time, open, high, low, close, volume, symbol, resolution, lastUpdated, type
```

### OHLC Closed — `ohlc_closed.{resolution}.{encoding}`
Cùng schema OHLC.

### Expected Price — `expected_price.{board_id}.{encoding}`
```
marketId, boardId, symbol, isin, closePrice,
expectedTradePrice, expectedTradeQuantity, time { Seconds, Nanos }
```

### Market Index — `market_index.{market_index}.{encoding}`
Input: `market_index` (không cần symbols)

```
indexName, changedRatio, changedValue,
fluctuationSteadinessIssueCount, fluctuationDownIssueCount,
fluctuationUpIssueCount, fluctuationLowerLimitIssueCount,
fluctuationUpperLimitIssueCount, fluctuationDownIssueVolume,
fluctuationUpIssueVolume, fluctuationSteadinessIssueVolume,
currencyCode, indexTypeCode, lowestValueIndexes, highestValueIndexes,
priorValueIndexes, valueIndexes, contauctAccTrdVal, contauctAccTrdVol,
blkTrdAccTrdVal, blkTrdAccTrdVol, grossTradeAmount, totalVolumeTraded,
marketIndexClass, marketId, tradingSessionId, transactTime { Seconds, Nanos }
```

### Foreign Investor — `foreign.{board_id}.{encoding}`
Input: `symbol`, `board_id`

```
marketId, boardId, tradingSessionId, symbol, transactTime,
foreignInvestorTypeCode, sellVolume, sellTradedAmount,
buyVolume, buyTradedAmount, totalSellVolume, totalSellTradedAmount,
totalBuyVolume, totalBuyTradedAmount, foreignerOrderLimitQuantity,
foreignerBuyPossibleQuantity
```

### Estimated VN30 — `estimated_market_index.{market_index}.{encoding}`
Input: `market_index` (hiện chỉ hỗ trợ VN30)

```
indexName, valueIndexes, changedValue, changedRatio,
fluctuationUpIssueCount, fluctuationDownIssueCount,
fluctuationSteadinessIssueCount, grossTradeAmount, totalVolumeTraded,
time   <-- STRING, không phải object
```

### Session — `session.{product_group_id}.{board_id}.{encoding}`
Input: `tsc_prod_grp_id`, `board_id`

```
marketId, boardId, eventId, tradingSessionId, tscProdGrpId, time (ISO string)
```

### Market Index Influence — `market_index_influence.{market_index}.{resolution}.{encoding}`
Input: `market_index` (`VNINDEX, VN30, VN100, HNX, HNX30`), `resolution` (`1, 7, 14, 30`
ngày). VNINDEX & HNX chỉ hỗ trợ `resolution = 1`.

```
index_name, data: [{ symbol, time{Seconds,Nanos}, influence, influenceRatio,
                     proportion, changeRatio, changeValue, price,
                     totalVolumeTraded, grossTradeAmount }]
```

---

## Sai lệch ĐÃ ĐO giữa tài liệu này và server thật (2026-10-09)

Đo bằng `DNSE_API_KEY`/`DNSE_API_SECRET` thật, subscribe `quote` trên ACB:

**Frame thật nhận được (top_price, `T=q`)**
```json
{"T":"q",
 "bid":[{"price":20.1,"qtty":14320},{"price":20.05,"qtty":10620},{"price":20,"qtty":43340}],
 "boardId":"G1","isin":"VN000000ACB8","marketId":"STO","symbol":"ACB",
 "multicastReceiveTime":{"Nanos":911050113,"Seconds":1791531378},
 "offer":[{"price":20.15,"qtty":520},{"price":20.2,"qtty":2730},{"price":20.25,"qtty":2220}],
 "time":{"Nanos":237000000,"Seconds":1791531382}}
```

| # | Tài liệu nói | Server thật gửi | Mức |
|---|---|---|---|
| 1 | `bid[].quantity` / `offer[].quantity` | **`qtty`** | **cao** — code theo doc sẽ ra 0 khối lượng, im lặng |
| 2 | `totalOfferQtty`, `totalBidQtty` | **không thấy** trong frame | trung bình |
| 3 | không có field `T` | có `T` (đánh dấu loại: `q`=quotes, `e`=expected price) | thấp — code đã dùng đúng |
| 4 | không có `multicastReceiveTime` | **có** | thấp |
| 5 | `expected_price` có `closePrice` | **không thấy** `closePrice` | thấp |

**Còn chưa đo được** (probe chạy ngoài phiên giao dịch, chỉ 2/8 kênh có dữ liệu):
`tick`, `tick_extra`, `security_definition`, `foreign`, `ohlc`, `ohlc_closed`,
`market_index`, `estimated_market_index`, `session`, `market_index_influence`.

**Mâu thuẫn con số giới hạn:** tài liệu ghi *"200 streams/connection"*, server báo
`rate_limit.subscriptions_max = 100`. Chưa rõ "stream" và "subscription" là cùng đơn vị.

**Heartbeat:** tài liệu Case 3 nói client gửi **PONG** chủ động; code
`websocket.py:417` gửi `{"action":"ping"}`. Chưa xác minh server chấp nhận `ping` từ
client hay bắt buộc `pong`. Ngoài ra `PONG_DEADLINE_SECONDS = 60.0` (`websocket.py:102`)
**được định nghĩa nhưng không dùng** — không có cơ chế nào phạt khi quá 1 phút.
