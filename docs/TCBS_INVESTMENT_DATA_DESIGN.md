# TCBS Investment Data Design

**Version:** 0.1 (draft — đang thảo luận)
**Tạo:** 2026-05-20
**Phạm vi:** Thiết kế tổ chức dữ liệu cho hệ thống quản lý đầu tư chứng khoán dựa trên TCBS API.

---

## 1. Nguyên tắc cốt lõi

### 1.1 Giới hạn của TCBS API

| Giới hạn | Hệ quả |
|---|---|
| API chỉ trả về trạng thái **hiện tại** (snapshot) | Phải tự lưu lịch sử theo thời gian |
| Tape/tick chỉ là **hôm nay** | Phải flush vào DB cuối phiên, không backfill được |
| Minute OHLCV ~90–180 ngày lookback | Nếu cần lịch sử dài hơn → bổ sung KBS/VCI |
| JWT OTP là **one-time-use** | Lưu JWT vào Redis/env, dùng lại suốt phiên |
| `get_balance` / `get_purchasing_power` có thể 403 | Tùy scope API key; cần kiểm tra khi onboard |

### 1.2 Ba tầng lưu trữ

```
┌─────────────────────────────────────────────────────────────┐
│  HOT  — Redis           TTL ngắn (1 phiên)                 │
│         Tape realtime, BSA realtime, JWT token             │
├─────────────────────────────────────────────────────────────┤
│  WARM — PostgreSQL      Query nhanh, lịch sử vừa           │
│         OHLCV, holdings snapshot, orders, balance, BSA     │
├─────────────────────────────────────────────────────────────┤
│  COLD — Object storage  Lịch sử dài, ít query              │
│         Raw JSON từ TCBS, tape archive theo phiên          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Domain A: Market Data

### 2.1 Bảng dữ liệu

| Bảng | Nguồn TCBS | Tần suất cập nhật | Tầng |
|---|---|---|---|
| `ohlcv_daily` | `Quote.history(1D/1W/1M)` | EOD ~15:35 | WARM |
| `ohlcv_minute` | `Quote.history(1m–1H)` | Intraday, backfill ~90 ngày | WARM |
| `tape_intraday` | `get_intraday_history()` | Realtime → flush cuối phiên | HOT → WARM |
| `bsa_realtime` | `get_bsa()` | Realtime | HOT |
| `bsa_15m` | `get_bsa_15m()` | Intraday | HOT → WARM |
| `bsa_month` | `get_bsa_month()` | 1 lần/ngày EOD | WARM |
| `ticker_info` | `get_ticker_info()` | 1 lần/tuần hoặc on-demand | WARM |

### 2.2 DDL

```sql
-- OHLCV ngày: partition by year
CREATE TABLE ohlcv_daily (
    symbol      VARCHAR(10) NOT NULL,
    date        DATE NOT NULL,
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    volume      BIGINT,
    source      VARCHAR(10) DEFAULT 'tcbs',
    PRIMARY KEY (symbol, date)
) PARTITION BY RANGE (date);

CREATE TABLE ohlcv_daily_2025 PARTITION OF ohlcv_daily
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE ohlcv_daily_2026 PARTITION OF ohlcv_daily
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- OHLCV phút
CREATE TABLE ohlcv_minute (
    symbol      VARCHAR(10) NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    interval    VARCHAR(5) NOT NULL,   -- '1m','5m','15m','30m','1H'
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    volume      BIGINT,
    source      VARCHAR(10) DEFAULT 'tcbs',
    PRIMARY KEY (symbol, ts, interval)
);

-- Tape (khớp lệnh từng tick) — lưu cuối phiên
CREATE TABLE tape_intraday (
    id              VARCHAR(40) NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    session_date    DATE NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    price           NUMERIC,
    volume          BIGINT,
    match_type      VARCHAR(10),   -- Buy / Sell
    accum_buy       BIGINT,
    accum_sell      BIGINT,
    is_highlight    BOOLEAN,
    PRIMARY KEY (symbol, session_date, id)
);

-- BSA 15m
CREATE TABLE bsa_15m (
    symbol          VARCHAR(10) NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    buy_vol         BIGINT,
    sell_vol        BIGINT,
    net_vol         BIGINT,      -- buy_vol - sell_vol
    PRIMARY KEY (symbol, ts)
);

-- BSA tháng
CREATE TABLE bsa_month (
    symbol          VARCHAR(10) NOT NULL,
    month           DATE NOT NULL,   -- first day of month
    buy_vol         BIGINT,
    sell_vol        BIGINT,
    net_vol         BIGINT,
    PRIMARY KEY (symbol, month)
);
```

---

## 3. Domain B: Account & Portfolio

### 3.1 Entity hierarchy

```
custody_code (vd: 105C836591)
  └── account (vd: 10000928344)           ← get_accounts()
        ├── AccountBalanceSnapshot        ← get_balance()       [mỗi ngày]
        ├── PurchasingPowerSnapshot       ← get_purchasing_power()
        ├── HoldingPositionSnapshot[]     ← get_holdings()      [mỗi ngày]
        │     ├── symbol, quantity
        │     ├── avg_cost (TCBS cung cấp hoặc tự tính)
        │     ├── market_value (enrich từ close price)
        │     └── unrealized_pnl
        └── Order[]                       ← get_orders()        [append-only]
              ├── order_id, side, status
              ├── symbol, qty, price
              └── filled_qty, filled_price, fee, tax
```

### 3.2 DDL

```sql
-- Snapshot số dư theo ngày
CREATE TABLE account_balance_daily (
    snapshot_date       DATE NOT NULL,
    account_no          VARCHAR(20) NOT NULL,
    cash                NUMERIC,
    total_market_value  NUMERIC,
    net_asset_value     NUMERIC,      -- NAV = cash + market_value
    purchasing_power    NUMERIC,
    PRIMARY KEY (snapshot_date, account_no)
);

-- Holdings snapshot theo ngày
CREATE TABLE holding_position_daily (
    snapshot_date   DATE NOT NULL,
    account_no      VARCHAR(20) NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    quantity        BIGINT,
    avg_cost        NUMERIC,          -- giá vốn bình quân (weighted average)
    close_price     NUMERIC,          -- giá đóng cửa ngày snapshot
    market_value    NUMERIC,          -- quantity * close_price
    unrealized_pnl  NUMERIC,          -- market_value - (quantity * avg_cost)
    unrealized_pct  NUMERIC,          -- unrealized_pnl / (quantity * avg_cost)
    weight          NUMERIC,          -- % trong toàn danh mục
    PRIMARY KEY (snapshot_date, account_no, symbol)
);

-- Order ledger — append-only, KHÔNG UPDATE record cũ
CREATE TABLE order_ledger (
    order_id        VARCHAR(40) PRIMARY KEY,
    account_no      VARCHAR(20) NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    side            VARCHAR(4) CHECK (side IN ('buy','sell')),
    order_type      VARCHAR(10),      -- LO, MP, ATO, ATC, MOK, MAK
    status          VARCHAR(20),      -- pending, filled, partial, cancelled
    order_qty       BIGINT,
    order_price     NUMERIC,
    filled_qty      BIGINT,
    filled_price    NUMERIC,
    fee             NUMERIC,          -- phí môi giới
    tax             NUMERIC,          -- thuế TNCN (bán: 0.1% giá trị)
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ,
    raw_json        JSONB             -- giữ nguyên raw response từ TCBS
);

-- Realized PnL — tính khi có lệnh bán khớp
CREATE TABLE realized_pnl (
    id              SERIAL PRIMARY KEY,
    account_no      VARCHAR(20) NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    sell_order_id   VARCHAR(40) REFERENCES order_ledger(order_id),
    sell_date       DATE NOT NULL,
    qty             BIGINT,
    avg_cost        NUMERIC,      -- giá vốn bình quân lúc bán
    sell_price      NUMERIC,      -- giá bán thực tế (filled_price)
    gross_pnl       NUMERIC,      -- (sell_price - avg_cost) * qty
    fee_tax         NUMERIC,      -- phí + thuế
    net_pnl         NUMERIC       -- gross_pnl - fee_tax
);
```

---

## 4. Domain C: Derived / Analytics

| Bảng | Nội dung | Tính từ |
|---|---|---|
| `indicators` | RSI, MA20/50/200, MACD, Bollinger | `ohlcv_daily` |
| `whale_signals` | Net buy/sell theo ngày/tuần | `bsa_month` + `bsa_15m` |
| `portfolio_performance` | Daily return, drawdown, Sharpe | `account_balance_daily` |
| `sector_allocation` | % từng ngành | `holding_position_daily` + `ticker_info` |

---

## 5. Analytics quan trọng

### 5.1 Equity curve & cumulative return

```sql
SELECT
    snapshot_date,
    net_asset_value,
    net_asset_value
        / FIRST_VALUE(net_asset_value) OVER (ORDER BY snapshot_date)
        - 1  AS cumulative_return
FROM account_balance_daily
WHERE account_no = '10000928344'
ORDER BY snapshot_date;
```

### 5.2 Sector allocation

```sql
SELECT
    t.sector,
    SUM(h.market_value)                                           AS sector_value,
    SUM(h.market_value) / SUM(SUM(h.market_value)) OVER ()       AS pct
FROM holding_position_daily h
JOIN ticker_info t USING (symbol)
WHERE h.snapshot_date = CURRENT_DATE
  AND h.account_no = '10000928344'
GROUP BY t.sector
ORDER BY pct DESC;
```

### 5.3 Win rate & trade stats

```sql
SELECT
    COUNT(*)                                    AS total_trades,
    COUNT(*) FILTER (WHERE net_pnl > 0)         AS winning_trades,
    ROUND(COUNT(*) FILTER (WHERE net_pnl > 0)
          * 100.0 / NULLIF(COUNT(*), 0), 1)     AS win_rate_pct,
    ROUND(AVG(net_pnl), 0)                      AS avg_pnl,
    SUM(net_pnl)                                AS total_pnl
FROM realized_pnl
WHERE account_no = '10000928344';
```

### 5.4 Cost basis (weighted average)

```
Mỗi khi buy lệnh khớp:
  new_avg_cost = (old_qty * old_avg_cost + filled_qty * filled_price)
                 / (old_qty + filled_qty)

Khi bán: ghi nhận avg_cost tại thời điểm bán vào realized_pnl.
```

---

## 6. Sync pipeline

### 6.1 EOD job (15:35 mỗi ngày giao dịch)

```python
# Celery task — chạy 15:35 mỗi ngày
@shared_task
def sync_account_eod(account_no: str, jwt: str):
    client = TCBSBrokerClient(...)

    # 1. Snapshot holdings (enrich_prices=True → close price đi kèm)
    holdings = client.get_holdings(account_no, enrich_prices=True)
    save_holding_snapshot(holdings, date.today())

    # 2. Snapshot balance
    balance = client.get_balance(account_no)
    save_balance_snapshot(balance, date.today())

    # 3. Sync orders mới (idempotent theo order_id)
    orders = client.get_orders(account_no)
    upsert_order_ledger(orders)

    # 4. Tính realized PnL từ orders filled mới
    compute_realized_pnl(account_no)

    # 5. Flush tape từ Redis → PostgreSQL
    flush_tape_to_db(date.today())
```

### 6.2 Intraday jobs

| Job | Tần suất | Action |
|---|---|---|
| `sync_tape` | Mỗi 30s trong giờ giao dịch | Pull tape → Redis |
| `sync_bsa_15m` | Mỗi 15 phút | Pull BSA 15m → Redis |
| `sync_ohlcv_1m` | Mỗi 1 phút | Pull OHLCV 1m → Redis |
| `flush_redis_eod` | 15:35 | Flush tất cả hot data → WARM |

---

## 7. Những gì TCBS không cung cấp (cần tự xây)

| Cần | Giải pháp |
|---|---|
| Lịch sử balance theo ngày | Celery job snapshot EOD |
| Giá vốn bình quân | Tính từ `order_ledger` (weighted avg) |
| Realized PnL | Match sell ↔ buy trong `order_ledger` |
| Phí giao dịch | Hard-code: 0.15% mua, 0.15% bán + 0.1% thuế TNCN |
| Order cũ hơn giới hạn TCBS | Load 1 lần ngay khi onboard, lưu vĩnh viễn |
| Minute data > 180 ngày | Bổ sung KBS hoặc VCI (public, không cần auth) |

---

## 8. So sánh provider cho market data bổ sung

| | TCBS | KBS | VCI |
|---|---|---|---|
| Auth | ✅ JWT (OTP) | ❌ Public | ❌ Public |
| OHLCV ngày | ✅ Đến IPO | ✅ Đến IPO | ✅ Đến IPO |
| OHLCV phút — date range | ❌ countBack từ now | ✅ start/end | ✅ start/end |
| Tape current day | ✅ page-based | ✅ page-based | ✅ cursor-based |
| BSA whale | ✅ Có | ❌ Không | ❌ Không |
| Order book depth | ❌ Không | ❌ Không | ✅ Có |

---

## 9. Câu hỏi mở (cần quyết định)

- [ ] **Cost basis method**: weighted average (đơn giản) hay FIFO (chính xác thuế hơn)?
- [ ] **Multi-account**: một user có thể có nhiều `account_no` dưới cùng một `custody_code`?
- [ ] **403 scope**: `get_balance` / `get_purchasing_power` bị 403 — cần đăng ký thêm scope với TCBS?
- [ ] **Benchmark**: so sánh performance danh mục với VNINDEX (dùng `ohlcv_daily` của VNINDEX)?
- [ ] **Minute data fallback**: nếu TCBS hết 90 ngày → tự động fallback sang KBS/VCI?
- [ ] **Alert**: thông báo khi position vượt ngưỡng drawdown (vd: -10%)?
