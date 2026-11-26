# Changelog

All notable changes to this project will be documented in this file.

### v3.10.0 — CafeF reference bug fixes (2026-11-26)

- `bulk_year(exchange, year, *, end_date=None, use_cache=True)`: clamp `EndDate`
  về `min(end_date, today_vn)`; cafeF trả HTTP 400 nếu gửi ngày tương lai.
  Thêm `bulk_range(exchange, start, end)` cho T+1 sync (3 request/ngày).
- Bulk cache: TTL 300 s + key theo resolved end date; `use_cache=False` bỏ qua
  **cả đọc lẫn ghi** (worker chạy dài không còn giữ mãi dữ liệu năm hiện tại).
- `reconcile_prices(..., exchange="HOSE")`: truyền sàn xuống `CafefReference`
  để so sánh adjusted của VCI/KBS với CafeF cho mã HNX/UPCOM.
- `reference/parser.py`: frame có thêm cột `date` (`datetime.date`) và
  `change_pct` (parse `"Thay đổi"` dạng `+1,65 (+4,01%)` → `4.01`).
- Không breaking change cho caller mặc định.

### Unreleased — v3.9.0: CafeF reference + `daily_bars` (2026-11-24)

> P1 bổ sung `Vnbroker.daily_bars(...)` (R1–R7) lên nền P0 (reference layer + adjusted route).

> **Không breaking change cho caller mặc định.** `adjusted` mặc định `True`
> (`None` ở adapter tầng API) giữ nguyên giá đã điều chỉnh từ KBS/VCI.
> `adjusted=False` giờ trả **giá thô thật** từ CafeF (ban đầu là fail rõ ràng,
> sau khi xác minh CafeF có cả 2 cột giá thì đổi sang route).

#### Added (P1)
- `Vnbroker.daily_bars(symbol|ALL, start, end, exchange, basis='raw'|'adjusted'|'both')` —
  thin wrapper trên `CafefReference.history` + `parse_records`, trả frame canonical có
  `close_raw`, `close_adjusted`, `open/high/low_raw`, `value`, `put_through_*`, `source`,
  `price_basis`, `coverage`, `fetched_at`. Default `start='2011-01-01'` kèm coverage metadata.
- `CafefReference.bulk_year(exchange, year)` — 1 request XLSX `Symbol=ALL`/năm/sàn,
  pacing ≥1 s global, retry 2 lần, cache `(exchange, year)`, `io.BytesIO` (không temp file).
  Perf đo: 34–40 s cho 101k dòng (peak), ~20 s cho 66k dòng.
- Coverage gate: frame rỗng được phân loại `coverage='missing'` (mã vắng trong ALL export)
  hoặc `'no_trading_days'` (mã có nhưng range không có nến) — không trả rỗng im lặng.
- `Vnbroker.reconcile_prices(frame, symbol, ...)` — monitoring, tách khỏi đường ghi; drift
  0,5% được phân loại rebase trước khi alert.

#### Added (P0)
- `vnbroker/reference/` — reference/cross-check layer **đọc-only**, KHÔNG đăng ký
  vào `ProviderRegistry`, `SUPPORTED_SOURCES` hay AUTO failover pool.
  - `Vnbroker.reference("cafef")` trả `CafefReference` (tên khác → `ValueError`).
  - `CafefReference.history(symbol, start, end)` trả frame riêng có
    `close_raw`, `close_adjusted`, `value`, `put_through_*`, provenance — khác
    schema 6 cột của tier-1 để tránh nhầm.
  - Fetch **XLSX primary + JSON fallback** (đo: 1 mã/năm 1,4 s so với 14,4 s;
    bulk 101k dòng XLSX 34–40 s so với ~82 phút của JSON).
  - `CafefReference.reconcile()` so tỷ lệ `provider.close / cafef.close_adjusted`,
    phát hiện rebase/double-adjust mà không sửa frame đầu vào.
- `KBS.Quote.history/fetch_multiple`, `VCI.Quote.history/history_async/fetch_multiple`
  và `vnbroker.api.quote.Quote.history`: tham số `adjusted: bool = True`.
  `False` route sang CafeF, gắn `attrs['source']/['data_origin']='cafef'`
  (và `df.source='cafef'` cho VCI). Interval khác `1D` → `ProviderBadRequestError`.
- Test: `tests/unit/reference/`, `tests/unit/explorer/test_quote_adjusted_parameter.py`,
  `tests/unit/core/test_adjusted_failover.py`,
  `tests/contract/test_cafef_reference_contract.py` (31 test targeted).

#### Changed
- `vnbroker.api.quote.Quote.history`: decorator `@retry` thêm
  `retry_if_not_exception_type(ProviderBadRequestError)` + `reraise=True`.
  Lỗi cố định không bị retry/bọc `RetryError`; network error vẫn retry theo
  `Config.RETRIES`. Exception cuối là exception gốc — behavior change có chủ đích.

#### Evidence
- `docs/evidence/KBS_VCI_RAW_PRICE_PROBE_20261124.md` — public KBS/VCI không có giá thô.
- `docs/evidence/CAFEF_PROVIDER_FEASIBILITY_20261124.md` — đo API CafeF.
- `docs/evidence/CAFEF_REFERENCE_LAYER_DESIGN_20261124.md` — thiết kế + vì sao tỷ lệ 0,935
  không phải double-adjust.

### 3.8.2 — fix P0 `ex_date=None` + lọc news trong corporate_actions (2026-11-20, tag `v3.8.2`)

> **Không breaking change.** `events()` và schema 14 cột giữ nguyên. Sửa lỗi
> P0 phát hiện khi vninvest re-probe bản 3.8.1.

#### Fixed
- `vnbroker.common.corporate_actions.normalize_events()`: `_pick` nhận thêm raw key
  thật của VCI là **`exrightDate`** (`vnbroker/common/corporate_actions.py:155` ở bản
  3.8.1 chỉ có `exRightDate`). Trước fix `ex_date=None` 100% dòng ⇒ mọi `group_id`
  thành `VNM:None`, làm vô nghĩa phép so sánh cùng ngày.
- Bỏ rows không phải sự kiện (`isEvent=False` hoặc thiếu `eventCode`) — endpoint
  `news-events-for-chart` trả lẫn 1000 dòng tin tức cộng 57 event (VNM).
- VNM live probe sau fix: 57 dòng, 0 dòng `ex_date=None`, 2 DIV cùng
  `2024-09-24` (950 + 1.500 VND) giữ riêng; facade trả `source='VCI'`.

#### Tests
- Golden fixture `tests/fixtures/vci_news_events_vnm_20261120.json` (57 event + 20 news).
- Fail-before: 5 failed / 1 passed; sau fix 25 passed (3 file unit slice).

### 3.8.1 — corporate action source: field số + API thống nhất (2026-11-20, tag `v3.8.1`)

> **Không breaking change.** `events()` giữ nguyên; các API mới là additive.
> Bump version theo chỉ thị Owner để phát hành code corporate action đã merge
> vào `main@5bcb3ca` (tag `v3.8.0` cũ trỏ `2cbf62e`, không chứa code này).

#### Added
- `vnbroker.common.corporate_actions`: `parse_event_title()` + `normalize_events()`
  trả DataFrame contract gồm `symbol`, `action_type`, `ex_date`, `cash_amount`,
  `stock_ratio_pct`, `source`, `source_event_id`, `raw_title`, `parse_status`,
  `group_id` (`"SYMBOL:YYYY-MM-DD"`, JSON-serializable), `fetched_at`.
- `VCI.corporate_actions(from_date, to_date, event_codes='DIV,ISS')` — gọi raw
  `news-events-for-chart` rồi normalize; `Company.corporate_actions()` facade
  qua `@dynamic_method` (cùng retry/fallback với `events()`).
- Test golden: VNM 3 cặp cùng `ex_date` thật (`2023-08-03`, `2024-09-24`,
  `2025-10-16`), FPT ESOP `0.5%`/`0.2%`, VCB tách `2025-03-12` / `2025-10-03`.

#### Fixed
- **ESOP ≠ cổ phiếu thưởng**: `ISS + %` chỉ set `stock_ratio_pct` khi title có
  `Cổ phiếu thưởng` / `Trả cổ tức bằng Cổ phiếu`. `Phát hành cho CBCNV tỉ lệ ...`
  ⇒ `parse_status='unparsed'`, không suy diễn số (audit v1 C-02).
- **TCBS auth docs/message**: `IMPLEMENTATION_SUMMARY.md:146`,
  `MIGRATION_GUIDE.md:36,44,47` và message `dividends()` hướng tới
  `TCBS_JWT_TOKEN` (JWT thật), không phải `TCBS_AUTH_TOKEN` (mã 48 ký tự, 401).

#### Ghi chú
- `record_date` / `payment_date` luôn `None` với VCI (provider không trả);
  không suy diễn từ `public_date`.
- Không đưa `adj_close`/`adj_factor` vào package — thuộc trách nhiệm consumer.

### 3.8.0 - sua 11 defect client DNSE OpenAPI + tra loi VNBROKER REQ-001..005 (2026-10-16, tag `v3.8.0`)

> Ban nay gop CA HAI dot `Unreleased` truoc do (sua 11 defect DNSE + tra loi
> REQ-001..005). `pyproject.toml`: `3.7.2` -> `3.8.0` — **minor vi co breaking**.
> Bump version la quyet dinh cua Owner.

#### Phan A: sua 11 defect client DNSE OpenAPI (2026-10-16)

Dot "test live DNSE" phat hien **11 defect client-side** — tat ca deu do duoc
 tren production thuoc (khong VPN) va deu da sua + **do lai live** lan cuoi.
Chi tiet: `docs/REPORT_DNSE_LIVE_20261016.md`, ke hoach
`docs/PLAN_DNSE_FIX_20261016.md`, audit `docs/AUDIT_DNSE_FIX_20261016.md`.

**Hai path bi ket luan "khong ton tai" hoac ra chi sai mot duoi dau gach:**

| Method | Truoc | Sau |
|:--|:--|:--|
| `get_working_dates` | tra hang `(dates rong, None)`, **0ms**, khong goi network | `GET /market/working-dates` → **200**, 257 ngay |
| `get_corporate_action_history` | `/accounts/{a}/corporate-actions` → **404** | `/accounts/{a}/corporate-action-history` → **200** |

**Breaking — doc truoc khi nang cap:**

| Do | Truoc | Sau |
|:--|:--|:--|
| DNSE `get_orders(order_category=...)` | tuy chon; khong truyen → server `400 INVALID_ORDER_CATEGORY` | **bat buoc**, khong co mac dinh |
| DNSE `get_trades_volume_profile(time=...)` | `int` | **`str` `yyyy-MM-dd`** (int → `DNSEValidationError`) |
| DNSE `get_trades_volume_profile(board_id=...)` | tuy chon | **bat buoc** |
| DNSE `get_order_history` | mot ve van chay | **ca hai ve hoac khong ve nao**; mot ve → raise |
| DNSE `marketType`/`orderCategory` sai gia tri | HTTP 200 + body rong, caller khong biet | `DNSEValidationError`, **truoc** khi co byte nao di ra |
| `trade.py` (noi bo) | 1 file 1352 dong | **tach 4 file** — API cong khai giu nguyen chu ky |

**Vi sao `order_category` KHONG co mac dinh `NORMAL`:** nguoi muon xem lenh
`STOP` ma quen tham so se nhan danh sach `NORMAL` day du trong mat va thieu — sai
du lieu ma trong nhu dung. Fail-open o tang NGU NGHIA du lieu te hon han mot
`TypeError` luc go. (Da can nhac phuong an B "chi validate" va C "mac dinh
NORMAL"; Owner chot A.)

**Sua liet (fail fast, truoc khi co byte nao di ra):**

| Do | Truoc | Sau |
|:--|:--|:--|
| 5 endpoint phan trang | milliseconds → `400 range exceeds…` | **tu chuan hoa ms → giay** |
| `get_market_index` | khac ngay → `400` tu server | raise `MARKET_INDEX_RANGE_NOT_SAME_DAY` + chi cua so hop le |
| `get_position_by_id(position_id=…)` | id rac → **server 500** | raise `INVALID_POSITION_ID` (**chac sai KIEU, khong chac sai GIA TRI** — id `0` van hop le) |

**Hang hoa moi (do duoc, khong doan):**

| Hang | Gia tri | Cach tim ra |
|:--|:--|:--|
| `BOARD_IDS` | `G1 G2 G3 G4 G7 G8` | 24 gia tri doan deu fail → bat chuoc `websocket.py:19` (`G<n>`) → quet `G0..G21` |
| `MARKET_IDS` | `STO HCX UPX STX DVX` | doc cot `marketId` trong chinh response cua `GET /instruments` |

> Hai hang **khong** validate cung: tap do tren MOT ma va MOT ngay, chac gia tri
> ngoai tap se chan oang moi khi DNSE them san moi.

**Cong moi:** `scripts/check_encoding.py` (vao `check_all.ps1`) — fail khi phat
hien double-encoding UTF-8. Ly do: dot nay mot file nguon bi `Get-Content -Raw`
(doc UTF-8 bang CP1252) ma **khong gate nao bat duoc**, vi file hong van decode
hop le la UTF-8. Cong nay cung bat duoc 1 file hong co san tu truoc
(`tests/unit/core/test_no_guest_quota_runtime.py`).

**Doi noi bo (khong breaking):** `trade.py` 1352 dong tach thanh `trade.py`
(622) + `trade_derivatives.py` (180) + `trade_conditional.py` (180) +
`openapi_passthrough.py` (354). API cong khai **giu nguyen chu ky**, khoa bang
`tests/contract/test_trade_public_surface.py` (47 method + 14 write-gated), xanh
TRUOC va SAU khi tach. Cach lam: dong bang API truoc, tach sau.

**Gate cuoi:** `check_all.ps1` FULL **exit 0** · pytest **2281 passed, 26 skipped**
(baseline 2177 => **+104**) · contract 149 · mypy-baseline 1266→1106 · encoding PASS
453 file · `ruff check tests` 13 KNOWN-RED **khong tang**.

**Da do lai live:** `scripts/probe_dnse_readonly.py` → `PASS=40 FAIL=16`, trong do
16 FAIL deu la **probe phu dinh co chu dich**. 11/11 defect da dong.

#### Phan B: tra loi VNBROKER REQ-001..005 (2026-10-14)

Tra loi van ban yeu cau `REQUESTS_TO_VNBROKER_20261014.md` cua vninvest
(ADR-006: broker SSOT qua vnbroker). Phan hoi day du:
`docs/RESPONSE_TO_VNINVEST_20261014.md`.

**Breaking co chu y (phia vninvest):** `marketType`/`orderCategory` sai gia tri
nay nem `DNSEValidationError` thay vi tra HTTP 200 + body rong. Code dang
"thu lai ALL/STOCK/EQUITY" se do loi ngay.

| Do | Truoc | Sau |
|:--|:--|:--|
| `marketType` sai | HTTP 200 + body rong, caller khong biet | `DNSEValidationError` (`INVALID_MARKET_TYPE`), **truoc** khi co byte nao di ra |
| `DNSEClient.__version__` | 3.4.0 (do) trong khi pyproject 3.7.2 | 3.7.2, va gate `version-sync` bay gio kiem ca metadata cua ban cai |
| `vnbroker.broker.capabilities` | khong ton tai | `{version, provider, registered, methods, features}` cho 3 lane |
| `DNSEClient.normalize_payload` | private `_to_dataframe` | public, nhan DataFrame/list/dict/envelope, `as_records=True` |
| Doc nhieu market | caller tu vong retry (chi chay duoc gia tri dau) | `get_positions_all_markets` / `get_order_history_all_markets`, moi dong co cot `market_type` |

**REQ-002 — khong khoi phuc code.** `/aion/v1/accounts/{accountNo}/orders/history`
khong co trong spec TCBS v1.0.0, va phuong an duy phu trong REQ ("phan trang
`get_executions` theo ngay") **khong thien hanh duoc**: `matching-details` khai
bao **0 tham so truy van**. Hai lane con lai (SSI, DNSE) da co `from_date`/
`to_date`. Xem `tests/contract/test_tcbs_order_history_contract.py`.

**No chua dong (can Owner quyet dinh):**

| No | Vi sao chua lam |
|:--|:--|
| Watchlist CRUD (REQ-003b) | Chua viet — tai thoi diem nay khong provider nao co watchlist API, nen khong co gi de goi. Da khai bao `unsupported` + contract test tu do neu provider mo API. Khong phai vi cam reverse-engineer. |
| Validate `market_type` o 12 method cua `Trade` | `trade.py` 1352 dong — vuot ngan sach 800. Khong them vao file da vuot ngan sach; can tach file truoc. |
| Spec DNSE chua ghim trong repo | DNSE khong co file OpenAPI commit kem sha256 nhu TCBS. `MARKET_TYPES` la tap **da tai lieu hoa**, chua phai enum do server cong bo. |

### 3.7.1 - HANG1 Row 1: chan su dung (2026-10-11, PR #5, tag `v3.7.1`)

Hang 1 cua bo tai lieu trien khai 2026-10-11 (doc theo thu tu:
`docs/DEPLOY_INDEX_20261011.md`). Moi so duoi day do bang **test chay that**,
xem `docs/TEST_REPORT_HANG1.md` de lay lenh tai lap.

| Do | Truoc (base `662e2ef`) | Sau |
|:--|:--|:--|
| Loop thu 2 dung chung lock async (BL-1) | `RuntimeError: bound to a different event loop` | 2 loop lien tiep xanh |
| Instance khac proxy/tenant dung chung key cache (BL-2) | key byte-identical | key phan biet (do tren class that VCI/DNSE) |
| 401/403/404/400/422 (BL-3) | `ConnectionError` + failover + cooldown | typed error + dung ngay + 0 cooldown |
| Pool tat ca cooling goi ke tiep (MA-1) | quet lai ca pool (cooldown vo hieu) | tra `[]`, fail-fast bang loi ro rang |
| KBS/VCI loi tra frame rong co cot (BL-6) | `record_success` + cache 24h | nem ra (10/12 test DID NOT RAISE pre-fix) |

**Breaking co chu y:** 400/401/403/404/422 khong con vao `except
ConnectionError` (ra `ProviderAuthError`/`ProviderNotFoundError`/
`ProviderBadRequestError`, la `vnbrokerError`). Host bat builtin se thay
chung noi len — can Owner xac nhan phia `vninvest` truoc khi merge.

### 3.7.0 — Rate-limit that + logger khong ro token (2026-10-10)

Dong nay dong **Wave 3 + Wave 4**. Moi so duoc do bang **call counter** va bang
**chay `redact_sensitive_data()` tren 10 chuoi** — khong doc tu tai lieu cu.

**W3 — rate-limit that (W3.0–W3.6):**

| Do | Truoc @ 4cd0f2d | Sau |
|:--|:--|:--|
| 429 tren source **co dinh** | **3** request / 1 lenh | **1** |
| 429 tren **AUTO**, 2 provider | **6** request / 1 lenh | **2** |
| `should_failover(RateLimitError(...))` | **`False`** | **`True`** |
| cooldown tu `Retry-After: 120` | **4.935s** (suy doan) | **119.98s** |

**Blocker da bat o audit vong 1:** ke thua `RateLimitError` cu co lai **lam AUTO
failover chet** — no khong phai `OSError` nen `should_failover` tra `False`, va
`base.py` se `raise` thay vi thu provider ke tiep. Sua bang cach cho no ke thua
them `ConnectionError` (MRO: `RateLimitError → NetworkError → vnbrokerError →
ConnectionError → OSError`).

**Blocker da bat o audit vong 2:** AC ban v2 do tren **duong sai**. Tôi kết luận
`common.data.Quote` khong retry 429 bang cach soi `hasattr(Quote.history,'retry')`
— nhung `@retry` **khong** phai noi retry xay ra: no nam **ben trong**
`_run_with_failover`. Do lai: **3** va **6** attempt. Vi vay
`common/data.py` — **duong nguoi dung that** — vao lat W3.

**W4 — logger (T4.1–T4.5):**

| Do | Truoc | Sau |
|:--|:--|:--|
| 10 chuoi thu, con sot token/OTP | **4/10** | **0/10** |
| 6 chuoi phai **khong** doi | **1/6** (`monkey=abc`) | **0/6** |
| `log.info("x=%s", {"a":1,"b":2})` | **`TypeError` → mat tron dong log** | `x={'a': 1, 'b': 2}` |

Nguyen goc: `SENSITIVE_PATTERN` yeu cau `tenbien [:=] giatri` va lop ky tu gia tri
`[^"\',\s}]+` **dung o dau cach**, nen `Authorization: Bearer <JWT>` chi an
`Bearer` con JWT lot. Va Python 3.13 bo `args=({...},)` thanh chinh dict, nen
filter duyet no ra **key**.

⚠ **L-R07 — cong cu "bao ve" bang cach pha du lieu con ng dung thi tot hon loi
no chan.** Cach tu nhien bat `otp 123456` la cho phep dau cach lam dau phan cach,
va do duoc pha:

```
'the user name is bob'    -> 'the user: "***REDACTED***" is bob'
'key note: read the file' -> 'key: "***REDACTED***" read the file'
```

Vi vay T4.4 **neo chu so** (4–8 digit) va T4.5 them **word boundary** — cai sau
cha `monkey=abc` bi che oan.

**5 minor do audit vong 5 bat va da sua (xem `docs/AUDIT_TIER1_WAVE34.md`):**

1. `bearer of the bond coupon` bi bop meo → `Bearer ***REDACTED*** …`; nay
   chinh la dang L-R07. Bay token phai **trong** co hinh credential moi bi che.
2. JWT `alg:none` (chuoi ky rong) lot nguyen van → chap nhan chuoi ky rong.
3. `retry_after` bi mat o duong `PROXY` + `ProxyMode.TRY` (moi proxy that →
   boc lai `ConnectionError` chung).
4. `details["url"]` cua 429 nhung **query string** — provider HMAC (DNSE, KBS) dat
   credential trong query; bay chi giu scheme+netloc+path.
5. `Retry-After: 0.5` in ra `"Retry after 0 seconds"`.

**CHUA CHAY (khong phai PASS):**

- **CI GitHub Actions** — job bi tu choi khoi dong do billing. Moi gate chay
  LOCAL qua `pwsh -File scripts/check_all.ps1`.
- Chua do live voi traffic TCBS/DNSE that trong dot nay.
- `broker/ssi/auth.py` dung `logging.getLogger` chuan → **khong** di qua
  `SensitiveDataFilter`. De la no (ngoai pham vi, lane tien that).

### 3.6.0 — Hop dong du lieu tang 1 (2026-10-10)

Dong nay dong **Wave 1 + Wave 2** cua `docs/PLAN_TIER1_PROVIDER_AGNOSTIC.md`.
Ba loi duoi day **dang xay ra voi nguoi dung** va deu sai **am thanh** — khong nem
loi, chi cho ra so sai. Moi so do duoc tren du lieu that (ma `TCB`, `VCB`).

**Sua 3 loi du lieu (uut tien cao nhat):**

| Loi | Truoc | Sau |
|:--|:--|:--|
| `match_type` lech casing giua provider | KBS `buy/sell/atc` · VCI `Buy/Sell/ATC`; `df[df.match_type=='Buy']` → KBS **0** dong, VCI **67** | ca hai `['ATC','Buy','Sell']`; KBS **74** dong |
| Cot `time` lech don vi luu tru | KBS `[us]` · VCI `[s]`; `DataFrame.concat` → **`object`** | ca hai `[ns, Asia/Ho_Chi_Minh]` |
| `market_cap` phong dai **1000 lan** | VCB **473 766 777.83** ty | **473 766.78** ty |

Nguyen nhan goc cua loi 1 chi la **mot dong**: `explorer/kbs/quote.py` goi
`.str.lower()` ngay sau `process_match_types`, pha dung hop dong vua lap 3 dong
tren. Do la **dung mot** choi `str.lower()` tren `match_type` trong toan repo.

Nguyen nhan goc cua loi 3: `api/snapshot.py` suy don vi gia tu **tham so**
`price_unit` thay vi doc `df.attrs['price_unit']` ma provider dan. Do live:
`price_board(price_unit=None)` va `price_board(price_unit='VND')` tra **cung**
`close_price = 56700`.

**Sua chuoi TCBS (5 loi, sua 1 chong du):**

1. `explorer/tcbs/auth.py` chi doc `TCBS_AUTH_TOKEN` — bien 48 ky tu ma server
   tra `401 validate.token.error` tren 4/4 endpoint.
2. `core/provider_pool.py` doi `TCBS_API_SECRET` — bien **khong ton tai** o dau.
3. `get_auto_candidates()` gap trong → khong bao gio dua TCBS vao AUTO.
4. Cong khong kiem duoc provider co credential bi lo khoi AUTO.
5. `common/client.py` **ghi de** token da dung cua provider bang bien sai.

Sau khi sua ca 5: `Vnbroker(source='TCBS').stock('TCB').quote.history()` → **20
dong** (truoc: `ConnectionError`).

**Cong moi:** `scripts/check_provider_consistency.py` (C0–C5) + `--self-test` 5
truong hop am, wire vao `check_all.ps1`. Cong nay **da duoc phong thu**: inject
lai 3 loi ma phien ban gate im lang → ca 3 deu exit 1, cay sach exit 0.

**Sua loi test phu thuoc may:** `pytest tests/unit tests/contract` xanh nhung
`pytest tests/` **14 failed** — do `tests/conftest.py` nap `.env` that vao
`os.environ`. Da them fixture `autouse` (`tests/isolation.py`).

**Dinh chinh 3 dieu phien truoc noi sai** (chi tiet: `docs/HANDOFF_TIER1_WAVE12.md` §2):
- "KBS intraday tz-naive" — **SAI**, no tz-**aware**; loi that la lech **don vi**.
- "TCBS nho bien sai" — **DUNG** nhung chi la 1/5 loi trong chuoi.
- "DNSE loi mang chop chon" — dung trieu chung, da tim ra nguyen nhan tang mang:
  TLS handshake toi `openapi.dnse.com.vn` **timeout**.

**Audit doc lap:** 2 vong, 0 blocker + 7 major + 4 minor (vong 1) va 0 blocker +
7 major + 4 minor (vong 2). **Tat ca da sua va co test khoa lai.** Chi tiet:
`docs/AUDIT_TIER1_WAVE12.md`.

**CHUA CHAY (khong phai PASS):** CI GitHub Actions (job bi tu choi khoi dong do
billing) · DNSE market data (TLS timeout) · doi chieu `market_cap` bang provider
thu hai (screener cua VCI/KBS tra 0 dong).

**Gate:** `check_all.ps1` exit **0** · pytest **1978 passed / 26 skipped** ·
contract **91** · mypy baseline 1138 (khong loi moi) · ruff 0.

### TCBS round 3: cong chan payload + tach derivatives.py 852L -> 462L (2026-10-10)

Round 3 **khong sua loi** — no **dung cong chan** roi bao cao Owner. Sua body write
mung khong co JWT thi co the **pha** thay vi chua.

**PHAT HIEN (do bang script, khong doan):** `requestId` trong toan spec = **0 lan**,
`refId` = **9 lan**. Cong quet **12** write method -> **38 lech**:
- `_gated_change_derivative_order` thieu **6 field `required`**
  (`accountId` `subAccountId` `orderNo` `refId` `nvol` `nprice`) => lenh sua lenh
  phai sinh nhieu kha nang bi TCBS TU CHOI hoan toan
- `_gated_place_derivative_order` thieu `volume` + `refId`; gui `quantity` nhung spec
  goi la `volume`
- `_gated_cancel_derivative_order` thieu `accountId` + `orderNo`; sai ten `orderId`
- `equity.py` gui thua `requestId` va `pinCode`

**Vì sao chua sua:** chua co JWT de probe; sua doi **public API**; neu tai lieu TCBS
**thieu** ma server that chap nhan `requestId` thi sua la pha. Can Owner chot.

**Cong moi `scripts/check_tcbs_bodies.py`:** doc payload that bang AST (theo bien,
bat ca `Assign` va `AnnAssign`, ca positional va keyword), tu kiem sha256 spec,
3 loai lech `EXTRA` / `MISSING` / `SUSPECT`. Baseline 38 dong **sinh bang
`--write-baseline`**. Self-test 10 case am thuc.

**Tach `derivatives.py` 852L -> 462L** bang `DerivativeWriteMixin` (`derivative_orders.py`,
354L). API khong doi: `inspect.signature` tren ca hai ban => **0 chu ky public khac biet**.
`_post`/`_write_request` (74 dong) bo, moi write di qua `_write_http.post_json` —
status map dong nhat toan lane (N8). **Khong con file TCBS nao vuot 800L.**

**Audit doc lap:** NEED_REVISION (1 blocker, 6 major) — sua tai `ee0fbc5`:
test tu tham chieu · cong bo sot 4/12 write method · baseline goi y `pinCode -> price`
(nguoi sua theo se **gui PIN vao o gia**) · `check_all.ps1` **khong ep** self-test ·
assert chet `or True` · so lieu test sai.

**Hoc them 5 lesson** vao `docs/LESSONS/` (19 -> 24, 3 -> 5 file), trong do
`gate-integrity.md` (L-G01..04) ghi lai chinh 4 loi cua cong do toi viet trong phien nay.
Day la ly do nhom nay ton tai: **cong moi luon can audit doc lap, khong tu chung minh duoc.**

Gate: pytest **1918 passed / 26 skipped** | contract 72 | ruff exit 0 |
mypy 1266->**1148** | ruff tests 13 KNOWN-RED khong tang | tcbs-coverage 47/48 |
tcbs-bodies 12 payload / 0 lech moi | lessons 24/40 | self-test 9/9 + 10/10.

**Chua probe server that** — chua co JWT (can Smart OTP tu app TCInvest).

### TCBS round 4: 38 lech payload -> 0, do duoc TTL 24h, 8/8 gate (2026-10-10)

Round 4 khac **3 doi tien** so voi 4 dot truoc: no duoc **JWT that** (da co san
trong `.env`, 1290 ky tu, RS256) => lan dau **do duoc** thay vi **doan**.

**1) 38 lech payload -> 0.** Owner chot "sua thang theo spec".
Cong `check_tcbs_bodies`: 12 payload, **0 lech moi**, baseline **rong**.
- equity: bo `pinCode` + `requestId` (spec `/akhlys/` chi co 5 field)
- derivatives: `quantity`->`volume`, `requestId`->`refId`, `orderId`->`orderNo`,
  `quantity/price`->`nvol/nprice`, `triggerPrice`->`soPrice`, `orderId`->`pkOrderNo`
- **them** `accountId` + `subAccountId` vao change/cancel (spec BAT BUOC, ban cu thieu
  => TCBS tu choi ca lenh)
- **bo** `quantity` + `price` khoi change_condition (lenh dieu kien chi sua duoc
  gia kich hoat)
- `callbackPoint`/`activationPrice`: spec `required` nhung `description` noi
  "only for TSO" — **suy thuan mo ta**, chi gui khi TSO. Cho 1 chon du nhat.

**2) TTL do duoc: 8 gio -> 24 gio.** `exp - iat = 86400s = 24.0 gio`.
Tai lieu TCBS deu ghi "~8 gio" — do la **suy doan, chua tung do**.
Sua `session.py` + 9 cho trong `docs/`. Tach `SESSION_TIMEOUT_SECONDS` (8 gio =
**timeout nhan roi**) khoi TTL token — mot comment sai lam ca hai sai.
**KHONG sua DNSE** — broker khac, chua do.

**3) 3 endpoint bi server tu choi** (quét 33 endpoint GET, 14 trả 200 that):
`hydros/*/pricing-policy` + `/risk` (403 `877006`) va `khaos/v1/loan` (400 `875001`).
Hai endpoint hydros **tung duoc bao PASS o Round 2 bang mock**.

**4) Tra loi 2 cau hoi cua Owner:**
- `/api/v1/derivatives/contracts`: **404 ca GET lan POST** => khong ton tai =>
  **khong noi**. Coverage giu 47/48, lan nay co bang chung server.
- 18 path da go o Round 1: **17** chet that. 1 path khong 404 nhung response
  **giong y het** mot path bia => wildcard, khong phan biet duoc => **khong mo lai**.

**5) 3 lo hong cua CONG do chinh toi tao ra khi sua** (L-G05/06/07):
- quet bo sot `payload["x"] = ...` -> bao MISSING cho field **co** gui
- `package_index` khoa theo **TEN key**; file moi sort truoc chiem mat key =>
  5 method derivative quet nham sang path co phieu, bao **9 lech SAI**
- `check_mypy_baseline.py` `text=True` ma khong khai `encoding` => decode loi =>
  `stdout=None` => `(proc.stdout or "")` => **gate XANH khi mypy that bai**
Khong ghi 2 loi dau vao baseline — chung la loi cua cong, khong phai no payload.

**6) 2 bug CO SAN:** `client.modify_order()` + `cancel_order()` truyen `pin_code`
cho method khong co tham so do => **TypeError moi lan goi**. Chung minh bang cach
goi that voi mock.

**7) 2 test DNSE ERROR -> skip.** Fixture `account_no` goi `get_accounts()` ma
khong boc lop bao ve: loi mang o fixture sinh **ERROR** (khong phai FAILED) =>
`_skip_if_transport_failure` **khong bao gio chay toi**. Nay 5/5 cho goi mang
deu co guard. Bang chung la loi moi truong: stash toan bo thay doi, chay tren
HEAD sach — **van dung 2 error do**.

**8) Equity tach file:** sua payload lam `equity.py` 808L vuot ngan sach (hoi quy
cua chinh toi). KHONG nen bang cach xoa comment — tach `equity_orders.py`
(242L) + `_equity_common.py` (66L) de tranh **import vong**. Con 546L.

**5 ket luan SAI cua chinh toi, dinh chinh tai cho** (§6 bao cao):
3 endpoint intraday "can sua" (thuc ra probe truyen chuoi literal `{ticker}`) ·
`eros` loi Accept-Language (do probe gui header hoc) · "18 path da chet" (thuc ra
17) · `khaos` "sai dinh dang accountNo" (thuc ra quyen) · "chua co JWT".

Gate: **8/8 PASS** | ruff 0 | mypy 1266->**1138** | contract 72 |
tcbs-bodies **0 lech** | lessons 24/40 | pytest **1919 passed / 30 skipped / 0 ERROR**.
`pytest-full` **xanh lan dau trong 4 dot**.

**CHUA CHAY:** khong goi write endpoint nao (tao lenh that tren tai khoan Owner
la viec chua duoc giao); `/khronos/*` chua the server xac nhan (tai khoan **khong
co derivative scope**); do tap `rc` that; CI khong chay (billing).

### TCBS round 4 (b): ban ghi tong hop + probe read-only + dinh chinh ba claim (2026-10-10)

**Dinh chinh sau khi da ghi bao cao — quan trong hon phan sua:**
1. **"Tai khoan thieu derivative scope" -> CHUA DU CAN CUU.** Suy ra tu claim `scopes`
   trong JWT, **khong co 401/503 nao chung minh**. Do lai: **ca 4** endpoint
   `/khronos/*` tra **cung mot** loi `500/210000` *"khong the thuc hien vao luc nay"*
   => loi theo **thoi gian**; tu choi quyen se tra **401/403**. Them,
   `/tartarus/v1/derivatives` — market data phai sinh — tra **200 that**.
   => `scopes` **khong phai** danh sach day du capability.
2. **Chi tiet toi BIA:** bao cao ban dau ghi *"probe luc ~17:00"*. **Toi khong ghi gio
   probe.** Nguyen nhan that: hom do la **THU BAY**, phai sinh VN nghi ca cuoi tuan.
3. **Chi tiet ngay:** co so `scopes` va 500/210000 thi nghieng ve *ngoai gio* hon
   *thieu quyen* — va chi probe trong gio giao dich moi chot duoc.

**Moi:** `scripts/probe_tcbs_khronos_readonly.py` — thu Mon chay **1 lenh**:
- chi GET; `WRITE_GUARD` + `READ_ALLOWLIST` chan path tao/sua lenh that.
  **Da chung minh:** chen `/khronos/v1/order/place` vao danh sach -> `AssertionError`.
- lay `custodyID` tu claim JWT va `accountNo` tu response API — **khong hardcode PII**
  (ban dau hardcode `custodyID`/`accountNo` that, da bo vi se commit vao repo).
- tu phan loai ket qua: 200 = du quyen · 401/403 = thieu quyen · 500/210000 = ngoai gio.
  **Khong doan** — in ca 3 truong hop de nguoi dung tu quyet.

**Moi:** `docs/TCBS_STATUS_20261010.md` — **mot nguon duy nhat**: da xong (14 muc) ·
ton dong (4 muc, xep muc do anh huong) · 3 claim da sua sai · **ke hoach Thu Hai**
4 buoc · co che an toan · su co chua giai thich.

Gate khong doi: 8/8 PASS | ruff 0 | mypy 1266->1138 | contract 72 |
tcbs-bodies 0 lech | lessons 24/40 | pytest 1919 passed / 30 skipped / 0 ERROR.

### He thong LESSONS: sai l?m du?c ghi lai + gate (2026-10-10)

Muc tieu: **sai l?m lap lai nhieu vong trong 3 phien TCBS lien tiep** (do bang mat,
gate chay 1 lan roi ket luan, tin loi agent). Gio co quy trinh de **tu dong** ghi lai
va **bat** sai l?m do.

**Noi dung — 19 lesson / 3 file** (`docs/LESSONS/`, theo nhom):

| File | Nhom | Lesson |
|:--|:--|:--|
| `evidence.md` | Do luong, bang chung, trich dan | L-E01..L-E07 (7) |
| `process.md` | Chia viec multi-agent, worktree, claim | L-P01..L-P06 (6) |
| `broker-risk.md` | **An toan tien that** | L-R01..L-R06 (6) |

Moi lesson deu co **Proof** (`path:line @ sha` / commit hash / output lenh) va
**CHECKLIST** tra loi duoc Co/Khong — khong nen "co the gay loi".

**Cuong cho biet**:

- `docs/LESSONS/INDEX.md` — bang tag -> file, quy tac fallback (an toan hon suy luan),
  va 3 quy tac cung C1 (file <= 120 dong) · C2 (tong <= 40 lesson) · C3 (bao du ten
  file da doc).
- `scripts/check_lessons.py` — **cong machine** kiem C1/C2/DRIFT, co `--self-test`
  9 case am thuc (CONTROL mau sach, C1, C2, 3× DRIFT, MISSING, exit 2).
- `.opencode/skills/project-lessons/SKILL.md` — skill **chi doc 1-2 file theo tag**,
  tra checklist ngan, khong doc ca so tay.
- Da **gắn vao `scripts/check_all.ps1`** (`lessons` + `tcbs-coverage`) va chay
  `--self-test` cho cac gate moi o moi vong.

**Ba sai l?m lon nhat duoc ghi lai (de lau hon se lap lai neu khong co quy trinh):**

1. **Tin con so trong tai lieu cu** — "13 endpoint chua dung" thuc te **9**; `refresh`
   trong spec = **0 lan** nen AC "tu refresh token" **khong thi hanh duoc**;
   `requestId` = **0 lan** trong spec nhung code van gui.
2. **Spec nam ngoai repo** — dot 1 doi chieu moi thu voi `~/Downloads`, khong ai tai
   lap lai duoc; lai ton tai 1 ban spec CU trong `docs/references/` **co du 18 path**
   da bi go, doi chieu nham se ket luan nguoc. Nay spec da commit + gate tu kiem sha256.
3. **HTTP 200 != thanh cong** — TCBS tra `rc` nghiep vu. `money.py._post` chi map
   401/403/5xx nen **400/404/422/429 rot qua**, `resp.json()` tra ve y nhu thanh cong.
   Bang chung do: 4/4 test `DID NOT RAISE` tren ban cu.

**Adapt khong copy:** cau truc lay tu `vninvestcharts-widget/scripts/check-lessons.cjs`
va `vninvest/docs/LESSONS/`; cong machine viet bang **Python** cho khop stack repo nay
(`scripts/` khong co Node). 3 sai lech co chu dich duoc ghi trong docstring: doc UTF-8
(console cp1252 lam mat tieng Viet co dau), bo BOM khi dem dong, regex DRIFT chiu dau.

**Khac biet co chu dich so voi vninvest:** vninvest co `docs/LESSONS/` nhung **khong co
cong machine** cho no — con day co. Khong sua vninvest.

### TCBS round 2: TokenManager + 9 endpoint — phu API 39/48 → 47/48 (2026-10-10)

Ba lát song song (Mode A, 3 worker trên 3 worktree). Base `b18e47b` → `68ab1ce`.

**Phủ API (đo bằng script, không đọc tài liệu):** spec 48 path · **47 đã nối** · còn 1
(`/api/v1/derivatives/contracts`, cố ý hoãn vì spec tự mâu thuẫn). Lệnh tái lập:
`python scripts/verify_tcbs_coverage.py`.

**Spec được commit vào repo lần đầu.** `docs/references/openapi-v1.0.0.json`
(sha256 `7f97d27b…42bd4a`). Đợt 1 chạy được nhưng spec chỉ nằm ở `~/Downloads` ⇒ không ai
tái lập lại được. `scripts/verify_tcbs_coverage.py` **tự kiểm sha256** và chuẩn hoá CRLF
trước khi băm (repo bật `core.autocrlf=true`, `.gitattributes -text` không thắng).

**TokenManager (`broker/tcbs/token_manager.py`, 303L).** Giải mã JWT `exp`/`iat` cục bộ
bằng stdlib — không thêm dependency, không gọi mạng. Cache trong bộ nhớ, seam
`token_provider`, callback `on_expiring`. **KHÔNG tự refresh**: đếm chuỗi `refresh` trong
toàn spec = **0 lần**; TCBS chỉ cấp token qua `apiKey + otp` (Smart OTP từ app TCInvest),
`apikey/extend` gia hạn **API key** chứ không phải JWT.

**Chặn bug 8 giờ bịa.** `auth.py` đọc `expiredTime` — field **không tồn tại** trong spec
(0 lần) ⇒ `session.py:87-90` rơi vào nhánh `else` và **tự chế** hạn 8 giờ. Nay lấy hạn từ
claim `exp`; không decode được thì **không bịa nữa** (`is_expired()` trả `None` để caller
quyết). `session.py` **không** bị sửa.

**9 endpoint mới.** 2 `gaia` (`apikey/info`, `apikey/extend`) · 4 tiền/vay
(`pricing-policy` + `deposit`/`withdraw`/`transfer`, 3 cái sau qua `@write_gate`) ·
`condition/cancel` (phái sinh, module mới) · `ananke/v1/securities`. Phủ 39 → **47/48**.

**`requestId` là field hư cấu.** Đếm trong toàn spec = **0 lần**, nhưng `equity.py` và
`derivatives.py` vẫn gửi. Lát mới **không** copy — sửa bản cũ để ở ticket riêng.

**Audit độc lập bắt 2 major, đã sửa trước khi push:**
- Write 4xx của money bị trả về **y như thành công** (`_post` chỉ map 401/403/5xx).
  Bằng chứng đo: trên bản cũ `90ead64` 4/4 test **DID NOT RAISE** cho 400/404/422/429;
  sau sửa 32 passed. Tách `_write_http.py` (155L) — `money.py` 791L → **773L**, vẫn dưới
  ngân sách.
- Không chỗ nào kiểm mã nghiệp vụ `rc` (TCBS trả HTTP 200 kèm `rc`). Thư viện **không**
  raise tự động — spec không liệt kê đủ tập mã và chưa có JWT để đo; thay bằng
  `describe_business_code()` + cảnh báo trong docstring.

**Gate:** `1881 passed / 26 skipped` (đợt 1: 1696 ⇒ **+185**) · contract 72 ·
`ruff check vnbroker` exit 0 · mypy strict OK (baseline 1266→1161) ·
`ruff check tests` **13 KNOWN-RED, không tăng**.

**Chưa probe server thật** — chưa có JWT (cần Smart OTP từ app TCInvest). Mọi AC về hành
vi runtime chỉ dựa trên **spec**, chưa quan sát thực tế.

### TCBS: nối OHLCV, viết lại WebSocket, gỡ 18 path legacy (2026-10-09)

Ba lát song song, mỗi lát một branch. **Toàn bộ kết luận được chứng kiến bằng
`openapi-v1.0.0.json` + `tcbs-openapi-v1.0.0.postman_collection.json` (48 REST
+ 5 WebSocket, khớp nhau 48/48).**

**S1 — `explorer/tcbs/bars.py` (mới, 369L).** Nối `GET /nyx/v2/stock/bars`
và `GET /nyx/v2/stock/bars-long-term` vào `quote.history()`. Trước đây `history()`
ném `NotImplementedError` cho daily OHLCV với lý do **sai** (docstring nói
"TCBS chỉ có intraday tick data"), trong khi spec có endpoint D/W/M.

Ba lỗi tìm ra khi code, đều dễ đi sai nếu chỉ tin test:
- `transform.py:402,406` cắt tz và cắt giờ ⇒ `bars.py` **không** đi qua
  `ohlc_to_df`; `tz_convert('Asia/Ho_Chi_Minh')` gọi **tường minh**. Dùng
  `Normalizer` thì frame UTC sẽ đi nguyên vẹn (`normalizer.py` chỉ
  `tz_localize` khi cột chưa có tz).
- `_INTERVAL_MAP` map `1M → 'ME'` (chuẩn pandas) nhưng spec TCBS quy định
  `resolution: D | W | M` ⇒ `bars.py` có map riêng.
- Server thật trả field **không có trong spec** (`dataT1: null`) ⇒ mọi field
  `.get()` an toàn, frame chỉ giữ 6 cột chuẩn.

**S2 — `explorer/tcbs/websocket.py`.** Tầng wire sai hoàn toàn: code gửi JSON,
protocol chính thức lại là **TEXT frame phân tách `|`**. Sửa 6 lỗi: auth
`d|a|||<base64>` thay vì header HTTP, chờ `d|0|{"success":true}` **trước** khi
subscribe, `d|s|`/`d|u|`, heartbeat `d|p|||` 2s, `ping_interval=None` (để nguyên
thì thư viện gửi ping RFC 6455 ⇒ server đóng `1002 Protocol Error`), và 2 endpoint
thesis có channel ID rời nhau (`normal` s|1-8, `derivative` s|21-27) nên không
dùng chung parser. Xoá bảng endpoint SIT (`openapisit.tcbs.com.vn` DNS FAIL,
đo được), giữ chữ ký `use_sit` nhưng nay cảnh báo bị bỏ qua.

**S3 — gỡ 18 path legacy** (`broker/tcbs/account.py` 13 path, `equity.py` 5
path) không có trong cả 2 tài liệu. Method gọi tới **ném lỗi rõ ràng**
(`_raise_removed`), không trả về rỗng im lặng. `account.py` 937→489L,
`equity.py` 980→798L.

> **QUAN TRỌNG — tiền tố `erebos`/`aion` KHÔNG phải tiêu chí "legacy".** Audit
> của tôi từng mô tả "19 path legacy là những path có tiền tố `erebos/v1`,
> `erebos/v2`, `aion`". **Câu này sai.** Spec chính thức **có** các endpoint
> dùng đúng các tiền tố đó — `/erebos/v2/digital/margin-info` và
> `/erebos/v2/digital/trans-hist-cashStatements` trong `money.py` **có** trong
> cả spec lẫn Postman, và `/eros/v2/get-profile/...` là thật. 18 path bị gỡ đã
> được **xác minh riêng từng cái** là không có trong spec. Tiêu chí đúng là
> **vắng ở path đó**, không phải **vắng ở tiền tố**.

**Ngoại lệ (quyết định Owner):** `/aion/v1/accounts` **giữ lại** — nó là
implementation của `@abstractmethod get_account_list()` (`broker/base.py:55`);
gỡ thì `TCBSBrokerClient` thành abstract. Path thay thế
`/aion/v1/customers/{custodyId}/accounts` cần `custodyId` — tức là cần chính
thông tin mà method đó sinh ra.

**Gate** (`scripts/check_all.ps1`, đo local vì CI không chạy do billing):
`pytest` **1696 passed / 26 skipped** (baseline 1497 ⇒ **+199 test**) ·
contract 72 · ruff exit 0 · `check_mypy_baseline` exit 0, baseline **1266→1161**
(fix 105 lỗi legacy) · `ruff check tests` giữ nguyên 13 lỗi KNOWN-RED.

**CHƯA CHẠY (không phải PASS):** **chưa probe server thật** — chưa có JWT TCBS
(cần Smart OTP từ app TCInvest). Vì vậy `countBack` và bản đồ resolution phút
là **hệ số ước lượng**, và mặc định 18 path là legacy **chưa** từng gọi server
(401 chạy trước routing nên không phân biệt được route có hay không).

**Còn nợ:** GĐ4 TokenManager · GĐ5 **13 endpoint** spec chưa dùng ·
`derivatives.py` 852L (>800L, `CLAUDE.md:15`, có sẵn, ngoài phạm vi lát này).

### Hai lỗi tìm ra bằng **live probe** (credential DNSE thật), không phải bằng test server giả

1. **`subscribe()` im lặng với Mapping.** Chữ ký thật là
   `subscribe(channels: List[str], symbols: Optional[List[str]])` nhưng truyền
   `{"quote": ["ACB"]}` sẽ lấy key làm channel, để `symbols` rỗng, và gửi
   `{"channels":[{"name":"top_price.G1.json","symbols":[]}]}`. Server trả
   `subscribed / active / symbols: None` ⇒ **người dùng tưởng đang stream mà thực tế không
   nhận gì, không exception, không cảnh báo.** Nay raise `TypeError` kèm **lời gọi đúng**,
   chặn trước khi gửi. `subscribe("quote", ...)` (bị tách thành 5 kênh một chữ) cũng bị chặn.
2. **`msgpack` không có trong `pyproject.toml`.** `encoding="msgpack"` raise đúng (giữ nguyên
   chính sách không fallback im lặng) nhưng người dùng phải tự đoán `pip install msgpack`.
   Nay có extra: `pip install "vnbroker[msgpack]"`, và message giải thích vì sao không fallback.

### Live probe — xác minh được những thứ test giả không bắt được

Đo với `DNSE_API_KEY`/`DNSE_API_SECRET` thật, **chỉ read + WebSocket auth**, không bật
write gate, không gọi method ghi:

| Hạng mục | Kết quả |
|---|---|
| HMAC-SHA256 signature | ✅ đúng, **không chứa secret** |
| WebSocket auth in-band | ✅ `session_id=conn_1791515486322648579` |
| **`rate_limit` shape** | ✅ **đúng như doc**: `{messages_per_second: 100, subscriptions_max: 100}` |
| Subscribe + dữ liệu thật | ✅ **19 frame**/12s; giá ACB 20.3, VNM 57.8; ISIN + timestamp thật |
| dry_run envelope | ✅ không lọt secret |

⇒ **Bản viết lại WebSocket chạy thật với server**, không chỉ khớp tài liệu.

**Giải tỏa được nghi ngờ của audit:** `subscriptions_max` tính theo **số kênh**, không phải
số cặp (5 kênh × 100 symbols = 500 pairs vẫn `active` khi `cap=100`) ⇒ `websocket.py:582`
đúng, nghi ngờ không thành finding.

**Phát hiện mới cần Owner trả lời:** host **`openapi.dnse.com.vn` không phản hồi**
(timeout 3/3 lần), trong khi `api.dnse.com.vn` (HTTP 401) và `ws-openapi.dnse.com.vn`
(HTTP 400) đều sống. DNS OK, TCP 443 mở, TLS bị đóng ngay. ⇒ **toàn bộ 25 method OpenAPI
không kiểm chứng được từ máy này**, kể cả `post_order`/`close_position`/
`create_trading_token`. Cần xác nhận: DNSE chặn geo/IP từ VN, host đang down, hay credential
thuộc môi trường nào. Chi tiết: `docs/PM_AUDIT_REPORT_20261009.md` §11.

## [Unreleased] - Write gate DNSE chuyen tang + gate local

### PM-01 — P0 write gate chuyen tu `Trade` xuong tang HTTP (blocker)

`eeb1965` dat hang rao tren `Trade` va lam dung 10/10 method. Nhung hang rao do
**vong qua duoc bang mot dong code hop le**: `Trade.as_openapi_client()` la method
**public**, tra ve mot `DNSEClient` **khong co** `_write_enabled`/`enable_write`,
va moi method tien that cua no deu `dry_run=False` mac dinh.

Do bang thuc thi (khong doc ten ham) — voi `Trade._write_enabled = False`:

```
POST   /accounts/orders?marketType=...&orderCategory=NORMAL   <-- dat lenh that
PUT    /accounts/A/orders/O
DELETE /accounts/A/orders/O
PATCH  /accounts/A/orders/O
POST   /positions/P/close
POST   /registration/trading-token
=> 6 request tien that, gate dang TAT
```

**Sua:** chuyen hang rao xuong `DNSEHttpClient.request` — **diem ngheo duy nhat** moi
request deu di qua, khong bypass duoc bang bat ky duong nao.

- Quyet dinh tu **HTTP verb** (`POST/PUT/PATCH/DELETE`), khong phai danh sach method.
  Them endpoint moi **khong the quen gate**, vi khong co gi de quen.
  Gate theo method se tai lap dung bug vua sua: them 1 endpoint = them 1 lo.
- `dry_run=True` **khong** can quyen — envelope la cach nguoi dung kiem tra payload
  truoc khi gui. Gate no la bien "xem" thanh hanh dong nguy hiem.
- `send_email_otp` **khong** gate: no la buoc dang nhap, gate no la dong luong dang
  nhap (quyet dinh Owner 2026-10-08). **Khong** gate `/registration/trading-token` —
  cap trading token la buoc uy quyen `post_order`.

**Breaking change:**

4. **`DNSEClient` gio co `write_enabled` (mac dinh `False`) va `enable_write()`.**
   Code dang goi `DNSEClient().post_order(...)` / `put_order` / `cancel_order` /
   `replace_order` / `close_position` / `create_trading_token` **se nhan
   `BrokerPermissionError(WRITE_NOT_ENABLED)`** cho den khi goi `enable_write()`.
   ```python
   client = DNSEClient(api_key=..., api_secret=...)
   client.enable_write()               # <- moi them
   client.post_order("STOCK", payload, trading_token)
   ```
   Doc (`get_*`, `get_ohlc`, `get_trades`, `get_instruments`) va `dry_run=True`
   **khong doi** — khong can `enable_write()`.
   `Trade.as_openapi_client()` / `Trade._get_openapi_client()` truyen tiep quyen
   write cua `Trade`, nen `trade.enable_write()` van la mot diem bat buoc duy nhat
   tren duong `Trade`.

Bang chung fail-before / pass-after: `tests/unit/connector/dnse/test_write_gate_layer.py`
(**11 test moi**) — truoc **6 failed / 4 passed**, sau **11/11 passed**. Probe doc lap
(viet truoc khi sua, khong dung test cua ho) do lai tu **6 request => 0**.
`test_dnse_endpoint_contract.py` bo sung `write_enabled=True` trong fixture: bo test do
dung `blocked.invalid` nen khong the gui ra ngoai, va no kiem path chu khong kiem gate.

### Gate local thay the CI (CI khong chay)

GitHub Actions cua repo nay **khong chay** — job bi tu choi khoi dong do billing
(`"spending limit needs to be increased"`). Lan chay thanh cong cuoi: **2026-10-02**.
Tu do toi nay **74 commit** merge ma khong gate nao chay.

- Moi: `scripts/check_all.ps1` — 1 lenh, exit code that, co `-Quick` va `-SelfTest`.
- `CLAUDE.md` + `HANDOFF_DNSE_ROUND2_20261009.md`: ghi ro CI **CHUA CHAY** va
  `mypy --strict` la **no-op** (ca hai lenh deu 1207 loi y het).

## [Unreleased] - DNSE round 2: write gate, ro credential, failover, WebSocket

**Breaking changes - doc truoc khi nang cap:**

1. **WebSocket DNSE viet lai hoan toan** theo protocol provider hien tai. Client cu sai
   o **moi mat** (host, auth, HMAC, nonce, subscribe, ten kenh, heartbeat, phan loai
   message) nen khong mot request nao cua no ra duoc.
   - Host: `wss://openapi.dnse.com.vn/ws` -> `wss://ws-openapi.dnse.com.vn/v1/stream`
   - Auth chuyen tu HMAC trong query string sang message `{"action":"auth"}` in-band
   - `subscribe` chuyen tu `channels:[str]` phang -> `channels:[{name,symbols}]`
   - Ten kenh cu (`quote`, `trade`, `sec_def`, ...) **giu lam alias** nen code goi cu
     khong vo. Ten wire day du (`tick.G1.json`) cung chay duoc.
   - Heartbeat chuyen tu WS protocol frame sang **application-level `{"action":"pong"}`**
     (server gui PING moi 3 phut, doi PONG trong 60s, neu khong close code 1008).
   - Symbols nay tu **UPPERCASE**; subscribe **truoc** khi auth se bi tu choi.
2. **10 method tien that cua DNSE moi can `trade.enable_write()`**:
   `set_deal_pnl_config`, `set_account_pnl_config`, `close_deal`,
   `place_conditional_order`, `cancel_conditional_order`, `post_order`, `put_order`,
   `cancel_order_openapi`, `create_trading_token`, `close_position`.
   Truoc day chi 4 method co hang rao; **do bang thuc thi** cho thay
   `Trade(api_key, api_secret)` khong goi `enable_write()` van gui **7 request that**.
3. **5 method truoc do khong co tham so `dry_run` nao** (luon gui, khong co loi thoat):
   `set_deal_pnl_config`, `set_account_pnl_config`, `close_deal`,
   `place_conditional_order`, `cancel_conditional_order` - nay da co.

**Sua loi:**

- **Ro credential trong envelope dry-run cua DNSE** (nghiem trong): chi `trading-token`
  duoc che bang `if` hardcode, nen **`X-Signature`** (chuoi HMAC day du) va
  **`x-api-key`** - gui tren **moi** request - in nguyen van. Nay dung chung `Redactor`.
  Cung luc do sua luon nguyen nhan goc trong `Redactor`: set luu key theo nhieu cach
  viet trong khi cho tra lai chuan hoa `-` -> `_`, khien **moi entry viet bang dau gach
  la chet vinh vien** (`x-api-key`, `X-Signature`, `smart-otp` deu lot). Ba entry point
  (`redact_dict` / `redact_headers` / `redact_url`) gio dung chung mot matcher.
- **3 path DNSE sai**: `close_position` -> `/positions/{id}/close`,
  `get_position_by_id` -> `/positions/{id}`, `send_email_otp` ->
  `/registration/send-email-otp` (khong gui body).
- **Failover parity**: `bulk_router.PROVIDER_ERRORS` co `OSError` con
  `source_router.should_failover` thieu => toan bo ho loi mang (DNS, SSL, connection
  reset, `requests.*`) khong failover o duong single-symbol trong khi duong bulk van
  chay. Loi code provider (`TypeError`/`ValueError`/`AttributeError`) van lot len nhu cu.
- `Trade` nhan them tham so `api_base_url` de cau hinh ho API **legacy**
   (`api.dnse.com.vn`, **25 method** dung host nay - SDK khong nhac toi; so do la
   25, khong phai 32 nhu ghi o ban nhap ban dau). Mac dinh **khong doi**.

**Khong sua (co chu dich):**

- `post_order` giu nguyen `accountNo` trong **payload**. **SDK chinh thuc mau thuan voi
  doc cua ho**: doc mau `post_order(market_type, payload, trading_token, order_category)`
  khong co `account_no`, SDK thi them vao path. `vnbroker` khop doc.
- `dry_run` giu mac dinh `False` de **khop SDK chinh thuc** (`client.py:473`). An toan
  den tu `enable_write()`. Doi sang `True` nhu 4 method cu se bien "gui tien ngo y muon"
  thanh "lenh bien mat im lang" - te hon.
- 4 method phien/OTP (`login`, `get_trading_token`, `login_and_get_trading_session`,
  `send_email_otp`) **khong** gate - gate se hong luong dang nhap.
- **`vninvest` khong can thay doi**: grep toan repo cho `DNSEWebSocketClient` va cac ten
  kenh cu deu **0 ket qua trong code** (chi co prose trong docs/ledger).

Chi tiet day du + danh sach viec con lai: `docs/HANDOFF_DNSE_ROUND2_20261009.md`.

## [3.5.0] — Kiến trúc hai tầng + an toàn đường giao dịch

**Breaking changes — đọc trước khi nâng cấp:**

1. `quote.history()` qua `Vnbroker` trả cột `time` **tz-aware** (`Asia/Ho_Chi_Minh`)
   thay vì tz-naive, và được **lọc theo `start`/`end`**.
   - Lý do: provider trả tz khác nhau (VCI tz-aware, KBS/DNSE/SSI tz-naive) khiến
     `pd.concat` sinh dtype `object`; VCI còn trả nến ngoài khoảng yêu cầu **không báo lỗi**.
   - Nếu code bạn so `df["time"]` với timestamp naive: dùng `.dt.tz_localize(None)`.
   - Gọi provider trực tiếp (`VCIQuote(...).history()`) **không đổi**.
2. `connector/dnse`: `place_order` / `cancel_order` / `deposit_derivative_margin` /
   `withdraw_derivative_margin` nay cần `trade.enable_write()` trước khi gửi thật.
   Mặc định `dry_run=True` (an toàn). Trước đây lệnh gửi ngay, không có hàng rào.
3. SSI **không còn retry tự động** trên POST đặt lệnh (chống double-submit).
   Đã tái hiện được: trước đây 1 lời gọi → **5 POST thật** khi response mất.
   - Hãy truyền `clientRequestId` khi định thử lại; key được gắn vào exception.

**Tính năng mới:**

- **Tầng 1 — dữ liệu ẩn danh, không cần biết provider.** `Market/Reference/Fundamental(auto=True)`
  và `Vnbroker(source="AUTO")`: hệ thống tự chọn provider ổn định và xoay vòng khi
  rate-limit / mất kết nối. Failover áp cho `history`, `intraday`, `price_depth`.
  **Mặc định vẫn là `"KBS"`** — không đổi hành vi cho người dùng hiện tại.
- Chuẩn hoá dữ liệu ở **một điểm duy nhất** (`_normalize_quote_result`): tz-aware,
  lọc biên, sort. Provider mới thêm vào tự động tuân thủ.
- `match_type` chuẩn hoá về `Buy`/`Sell`/`unknown` cho mọi provider (trước đó
  DNSE/SSI giữ nguyên giá trị provider → sai âm thầm).
- `Redactor.redact_url()` — chặn rò `api_key`/signature trong query string
  (`connector/dnse/websocket.py` trước đây log nguyên văn ở level INFO).

**Sửa lỗi hạ tầng:**

- **CI không chạy cho PR vào `dev`**: cả 4 workflow trigger `[main, develop]` nhưng
  repo không có branch `develop`. Đã đổi thành `[main, dev]`.
- `pytest tests/contract/` + `ruff` nay **chặn thật** (trước mọi bước đều advisory).
- `[tool.ruff]`: 2888 → 0 lỗi với rule set có chủ đích.
- `check_version_sync.py` quét cả `tests/` (trước gate xanh trong khi test đỏ).
- Reset baseline `mypy --strict` (ghi 556 dòng nhưng thực tế 1266 lỗi → gate luôn đỏ),
  hạn **2026-11-01** và hạn **được thực thi thật** (`baseline_is_expired`).
- Xoá `vnbroker/core/base/` — 164 câu lệnh code chết (registry thứ hai bị thay thế
  từ `dbcd81a`, 0 import). Bằng chứng ở `f5de70d`; gate ngăn tái sinh.

**Số liệu:** pytest **1001 passed** / 5 skipped · ruff 0 · version-sync 0 ·
mypy-baseline 0 · coverage **55%**.

### Sửa lỗi phát hiện bởi CI ngay sau khi đóng gói (v3.5.0 follow-up)

Ba lỗi này **chỉ lộ ra trên CI**, không thấy ở máy dev — và là nguyên nhân release
v3.5.0 bị đánh dấu đỏ. Đã tái hiện và sửa, không reset baseline.

1. **`fillna(None)` — phụ thuộc phiên bản pandas.** `common/data.py:83` gọi
   `.fillna(symbol)` với `symbol=None`. pandas **2.x** ném
   `ValueError: Must specify a fill 'value' or 'method'.`; pandas **3.x** bỏ qua.
   Máy dev dùng pandas 3.0.2 nên xanh, CI dùng 2.x nên đỏ trên cả 3 OS.
   → Sửa bằng `if symbol is not None:` + `test_pandas_version_compat.py` chặn
   tái phát ở mức AST (vì test runtime ở máy pandas 3 không bắt được).
   **Đã verify bằng pandas 2.2.3 thật: trước sửa đỏ, sau sửa xanh.**
2. **Thiếu stub `types-requests` trong `[lint]`.** Không có nó, số lỗi mypy phụ
   thuộc môi trường: CI (Python 3.11) báo 14 lỗi "mới" cho cùng một commit mà máy
   dev báo 0. → Bổ sung stub vào `lint` extra, và sửa 3 lỗi thật phát lộ ra:
   `dict` không annotate → `Dict[str, Any]` ở `dnse/trade.py` và `proxy_manager.py`;
   `_telegram_photo` khai báo `-> requests.Response` nhưng trả `response.json()`
   (bug annotation thật) → `Dict[str, Any]` + `cast`.
   **Kết quả: 33 lỗi strict được sửa thật, không phải nới baseline.**
3. **`import file mismatch` — 7 basename trùng giữa các thư mục test.**
   Thiếu `__init__.py` nên `test_quote.py` ở `tests/unit/explorer` và
   `tests/integration/explorer` đụng nhau, làm **toàn bộ** collection fail.
   → Thêm 16 `__init__.py`. `pytest tests/` giờ thu thập 1090 test, exit 0.
4. **2 test integration lỗi thời** (đã xoá cùng đợt dọn tham chiếu cũ) — test cũ assert
   `SUPPORTED_SOURCES == ['KBS','VCI','TCBS','DNSE']` (thiếu SSI từ 3.4.0 và AUTO
   từ 3.5.0), và kỳ vọng `crypto()` ném `NotImplementedError` trong khi nay là
   `ValueError` (crypto đã có provider BINANCE thật từ 3.4.0). Bất biến
   `SUPPORTED_SOURCES` nay được giữ ở `tests/unit/common/test_stock_ssi.py::test_supported_sources`.
   → Chuyển sang bất biến + kiểm đúng hành vi.

**Số liệu sau sửa:** pytest **1064 passed** / 29 skipped (toàn bộ `tests/`) ·
1006 passed trên pandas 2.2.3 · ruff 0 · version-sync 0 · mypy-baseline 0.

---

## [Unreleased]

### Fixed — TIER1-ENGINE-v3: Tier-1 data engine actually meets its own DoD

Kế hoạch `docs/PLAN_TIER1_ENGINE.md` (WP-1..WP-5) đã code xong ở `b51b2a8` và được
đóng bằng 5 claim `done`. **Đo lại thì DoD §9 của chính nó đạt 3/13**, và bulk **không
hoạt động chút nào**. Vòng này sửa để DoD thật sự đạt.

**Baseline đo được tại `e5d8133`:**
```
ProviderRegistry.list_available('quote')        -> []           # registry rỗng
get_provider('quote','kbs')                     -> ValueError: Available: []
VCI.fetch_multiple iscoroutinefunction()        -> True
BulkAPI.history(["ACB","VNM"])  (network blocked) -> shape (0, 7)
    attrs: {'sources_used': {}, 'failed': {}, 'requested': 2, 'returned': 0}
    network calls attempted: 0
```
0 dòng **và 0 lần gọi mạng** ⇒ thất bại âm thầm, không tốn một request nào.

#### Đã sửa

- **Registry tự đầy sau `import vnbroker`** (`core/registry.py`). Trước đó provider chỉ
  đăng ký khi có ai đó import `explorer/*`, nên đường bulk không bao giờ dựng được provider.
- **Bulk thật sự lấy dữ liệu** (`core/bulk_router.py`). Ba tầng hỏng độc lập: registry
  rỗng ⇒ `provider_class()` không chạy · fallback gọi method trên **class** nên `self` bị
  bind vào chuỗi symbol · `VCI.fetch_multiple` là `async classmethod` nên trả coroutine.
- **Bulk báo lỗi thật.** `attrs["failed"]` trước luôn là `{}` vì `_fetch_batch` nuốt mọi
  exception ở `:136`/`:153`; nay `errors[provider]` được set và `HealthRouter` được gọi.
  Lỗi lập trình (`TypeError`/`AttributeError`) **không** còn bị đổi thành `logger.warning`.
- **Circuit breaker của đường bulk thật sự hoạt động.** `bulk_router` upper-case tên
  provider nên health ghi vào khoá `("quote","VCI")` trong khi store đọc `['vci','kbs']`:
  sau 6 lần fail, `failures=0`, `in_cooldown=False` cho mọi provider, cộng dồn khoá không
  ai đọc rồi ghi xuống SQLite. Nay khoá ghi và khoá đọc khớp.
- **Ngày nghỉ thị trường không còn bị báo là lỗi.** Tiêu chí "không dùng được" nay là
  **schema**: 0 cột ⇒ provider hỏng; đủ cột + 0 dòng ⇒ ngày nghỉ ⇒ **thành công**. Đường
  bulk trước dùng "0 frame" nên mỗi ngày nghỉ đều ghi vào `failed` và hạ health của
  provider. `common/data.py` đã phân biệt đúng; nay hai nhánh **dùng chung một helper**
  (có test ép điều đó, để chúng không lệch nhau lần nữa).
- **Hết retry lồng nhau.** `intraday` và `price_depth` giữ `@retry` bên ngoài *và* bọc
  thêm `Retrying(3)` cho từng provider trong `_run_with_failover`. Đo bằng **đếm lời gọi
  provider**: `18 → 6`. `history` từng đã gỡ đúng, hai hàm kia bị bỏ sót.
- **`interval` được truyền tới router.** `BulkAPI.history` khai tham số nhưng không truyền
  ⇒ người dùng xin nến 1 phút và âm thầm nhận nến ngày.
- **`price_board` theo `self.source`** — trước hardcode `source="KBS"` ở **cả hai** chỗ
  (`Trading` và `Listing`), nên `source="AUTO"` vẫn ra KBS.
- **Gỡ đảo chiều phụ thuộc `core → api`.** `bulk_router` gọi `vnbroker.api.quote`; nay gọi
  thẳng `provider.history(parallel=True, symbols=[...])` — bridge **đã có sẵn** trong
  `explorer/vci/quote.py`. Bỏ được cả cạnh phụ thuộc lẫn một bridge trùng lặp.
- **Cache key không còn va chạm.** `_make_key` bỏ mọi tham số non-primitive nên các truy vấn
  khác nhau dùng chung một key; thêm nữa `None`/`"None"`, `0`/`"0"` và mọi DataFrame đều
  gộp về một token. Đo được cả lỗi **đọc nhầm payload**. Nay phân biệt theo kiểu, vẫn
  deterministic, và tham số bằng nhau **vẫn hit** (cache không mất tác dụng).
- **Rate limiter không còn treo.** `capacity = capacity or rate` khiến `rate < 1` cho
  capacity < 1 token, và `wait()` không có `max_wait` ⇒ lặp vô hạn, không log, không
  exception. Nay `capacity >= 1` và `wait(tokens, max_wait=…)` ném `TimeoutError`.
- Xoá code chết: `_thread_local` (`core/utils/client.py`), `ProviderPool.get_provider`
  (0 importer), `core/base/` (611 dòng).

#### Đã cố ý KHÔNG sửa

- **Session HTTP dùng chung.** Kế hoạch v2 ghi nó là race vì "cookie không khoá" — đo thì
  `requests` 2.33.1 có `RLock` trong cookie jar, A/B 3 vòng **1600/1600, 0 lỗi**. Sửa thứ
  không hỏng là tự tạo rủi ro mới. Chỉ xoá `_thread_local` chết.
- **`core/source_router.py`** và **`vnbroker/explorer/*`** — ngoài phạm vi.

#### Gate

- **DoD đo được: 3/13 → 26/26.** Nhưng con số `3/13` trước đây **không ai tái lập được**:
  script đo nằm ngoài repo. Nay `tests/acceptance/test_tier1_dod.py` là gate thật trong
  repo. Chứng minh: trên cây baseline `e5d8133` nó **18 failed / 8 passed**; tại HEAD
  **26/26**.
- `pytest tests/unit tests/contract` **1128 → 1237 passed** · `pytest tests/` **1173 → 1308**
  · `ruff` exit 0 · `check_mypy_baseline.py` exit 0 · `check_version_sync.py` exit 0
  · `python -m build` + `check_dist_contents.py` + `twine check` exit 0
  · `check-claims.cjs` PASS (20 claim, 0 conflict)
- **Coverage 58,15% → 60%** (ngưỡng ORANGE của `coverage-report.yml`).

#### CHƯA CHẠY — không được coi là xanh

- **GitHub Actions không chạy cho repo này**: job fail sau 2 giây với `steps: []` và
  `duration_ms: 0`; 10/10 run gần nhất trên `dev` đều `failure`. Mọi gate trên là
  **local**. Còn một lớp verify chưa chạy (matrix Python, Ubuntu, `-n auto --reruns 2`).
- **Bulk chưa từng chạy với mạng thật.** Đã chứng minh tới "provider thật được gọi và báo
  lỗi"; phần `VCI.fetch_multiple` async qua `httpx.AsyncClient` singleton trả frame trong
  thread `ThreadPoolExecutor` vẫn là **giả định chưa kiểm** — và đó là điểm then chốt.
- 23 integration test live: thiếu `DNSE_API_KEY`/`API_SECRET`/`ACCOUNT_NO`, `TCBS_API_KEY`,
  SSI key + OTP người dùng.
- `black`/`isort`/`bandit`/`safety`/`pip-audit`/`pytest-benchmark` không cài trong `.venv`.

#### Ngoài phạm vi — đã ghi nhận, chưa sửa

- **P0 `connector/dnse/trade.py`**: `_require_write` chỉ được gọi ở **4** chỗ; 9 method ghi
  (`:548`, `:628`, `:813`, `:950`, `:1101`, `:1119`, `:1141`, `:1164`, `:1206`) nhận
  `dry_run: bool = False` **mặc định** và forward thẳng, không gate nào. Sửa ~9 dòng.
- **`core/source_router.py:357` `should_failover` bỏ sót `OSError`** và
  `requests.exceptions.ConnectionError`, trong khi `bulk_router.PROVIDER_ERRORS` có
  `OSError`. Hai chính sách failover khác nhau cho cùng một lớp lỗi.
- **`core/utils/async_client.py:34`** định nghĩa class `TokenBucketRateLimiter` **trùng tên**
  với `core/utils/rate_limiter.py`, cài khác hẳn, chưa qua sửa VN-3; `_acquire_token` ở
  `:70-79` là `while True` không chặn trên.
- `core/utils/transform.py` `fillna('unknown')` vô điều kiện mọi provider + heuristic
  ATO/ATC ⇒ bóp méo `match_type` (DNSE `F`/`U` bị ghi đè `ATO`/`ATC`).
- `broker/security/redaction.py`: `x-api-key`/`x-apikey` không khớp bộ khoá ⇒ `X-Signature`
  lộ nguyên văn; `redact_headers` không dùng `SENSITIVE_KEYS`.
- `connector/dnse/core/http_client.py:53-55`: envelope dry-run chỉ mask `"trading-token"`,
  header thật gửi là `"Trading-Token"` ⇒ dry-run envelope là **full credential dump**.
- 12 file vượt quy tắc ≤800 dòng của `CLAUDE.md`, lớn nhất `common/data.py` 1873 dòng
  (trước 1800). Không cắt trong vòng này.

#### Quy trình

Chạy pipeline `multi-agent-workflow` Stage 0→8: 3 slice file-set rời nhau (19 path, 0
giao nhau) trên 3 worktree → Stage 2 audit plan trả `NEED_REVISION` (8 vấn đề chặn) → plan
v3 → Stage 5 audit code trả 0 blocker / **5 major** → vòng 2 sửa 5 major → re-audit của
supervisor **12/14** (2 FAIL là kỳ vọng sai của probe, đã ghi).

### Added
- **Hợp đồng tầng 1 (contract test)** — `tests/contract/` khoá bảo đảm mọi provider ẩn danh
  (VCI, KBS) trả về cùng schema: đủ cột chuẩn, `time` tz-aware, không có dòng ngoài khoảng
  `[start, end]`, thứ tự thời gian tăng dần.
- `tests/contract/test_layer_normalization.py` — 12 test khoá hợp đồng chuẩn hoá ở tầng `data.py`.
- **Failover tầng 1** — `Quote._run_with_failover()`: hệ thống tự chọn provider ổn định và
  tự xoay vòng khi gặp rate-limit / mất kết nối, dùng cơ chế `core.source_router`
  (`build_source_order`, `should_failover`, health store có cooldown). Kết quả được gắn
  vào `df.attrs["source_used"]` để debug.
- **Tuỳ chọn `auto=True`** trên `Market` / `Reference` / `Fundamental`, và `source="AUTO"`
  trên `Vnbroker`. **Mặc định giữ nguyên `"KBS"`** — không thay đổi hành vi cho người
  dùng hiện tại.
- `tests/contract/test_failover_tier1.py` — 8 test khoá hành vi failover.
- **Gate CI thực sự chặn (GĐ4):** `pytest tests/contract/` và `ruff check` chạy **không**
  `continue-on-error`. Trước đó mọi bước lint/type/security đều advisory.
- `[tool.ruff]` trong `pyproject.toml` — rule set nhỏ, có chủ đích (syntax error, undefined
  name, unused import/biến, mutable default). Baseline: **2888 → 0 lỗi**.
- `check_version_sync.py` quét cả `tests/` — trước đó gate xanh trong khi 3 test đỏ vì
  test hardcode version cũ.
- Sửa `params: Dict = {...}` dùng chung giữ các lần gọi ở 3 `explorer/*/screener.py` (B006).

### Security — đường tiền thật (P0, sau kiến trúc hai tầng)

- **SSI không còn retry mù trên POST đặt lệnh.** `SSIHttpClient.request` trước đây bọc
  mọi method trong `tenacity.Retrying` không phân biệt idempotent; `ConnectionError`
  xảy ra cả khi server **đã nhận lệnh** nhưng response mất → gửi lại lệnh trùng.
  **Đã tái hiện: 1 lời gọi → 5 POST thật.** Nay chỉ retry method idempotent
  (`GET`/`HEAD`/`PUT`/`DELETE`/`OPTIONS`); POST ném `BrokerNetworkError` với code
  `NETWORK_ERROR_NON_IDEMPOTENT` kèm hướng dẫn tra cứu `clientRequestId`.
- **`clientRequestId` được gắn vào exception** khi lỗi mạng xảy ra (`broker/ssi/equity.py`)
  — không có nó thì lần thử lại sinh key mới và dedupe phía server vô hiệu, tức vẫn
  là double-submit do người dùng bấm.
- **`connector/dnse/trade.py` có hàng rào ghi.** Trước đây `place_order`,
  `cancel_order`, `deposit_derivative_margin`, `withdraw_derivative_margin`
  **không có** `dry_run`, **không có** `write_gate` → tiền đi thật ngay.
  Nay: `dry_run: bool = True` (an toàn) + `Trade.enable_write()` tắt mặc định;
  `dry_run=False` mà chưa bật quyền thì ném `BrokerPermissionError`.
- Thứ tự trong `place_order`: **validate → guard → network.** Để guard trước validate
  sẽ khiến dry-run trả "OK" cho một lệnh mà lúc gửi thật chắc chắn raise — dry-run nói dối.

### Fixed — dữ liệu âm thầm & rò credential (P2)

- **`match_type` chuẩn hoá về một tập giá trị.** `process_match_types` trước đây là
  if/elif theo `source`, mỗi provider một cách viết (VCI `'b'`, TCBS `'BU'`, KBS `'B'`),
  và **DNSE/SSI không có nhánh nào** nên giữ nguyên giá trị provider. Hệ quả:
  `df[df.match_type == "Buy"]` cho kết quả khác nhau tuỳ provider, sai mà không ném lỗi.
  Nay dùng bảng mapping chung + chuẩn hoá hoa/thường → chỉ còn `Buy`/`Sell`/`unknown`,
  không NaN, provider mới tự động tuân thủ.
- **`Redactor.redact_url()`** cho URL có credential trong query string (client HMAC DNSE/KBS
  truyền `?api_key=...&signature=...`). `connector/dnse/websocket.py` trước đây log URL
  nguyên văn ở level **INFO** → rò `api_key` + HMAC signature. Đã bổ sung `signature`,
  `sig`, `trading_token`, `smart_otp`, `x-api-key` vào danh sách nhạy cảm.
- **Xoá `vnbroker/core/base/` — 164 câu lệnh code chết.** Đây là registry đầu
  tiên của dự án, đã bị `core/registry.py` thay thế ở commit `dbcd81a` ("registry merge")
  nhưng quên dọn. 0% coverage và **không module nào import** (đã quét toàn repo).
  Hai registry cùng tên khác API là bẫy cho người đọc mới. Bằng chứng hoạt động được
  lưu ở commit `f5de70d` trước khi xoá; `tests/unit/core/test_legacy_base_module.py`
  nay là gate ngăn tái sinh (đã kiểm chứng đỏ khi thư mục tồn tại).
- **Failover mở rộng sang `intraday` và `price_depth`.** Trước đó chỉ `history` xoay vòng
  provider — khi provider chính hết hạn, toàn bộ người dùng mất dữ liệu trong phiên dù
  hệ thống còn provider dự phòng.
- `_normalize_quote_result()` trong `vnbroker/common/data.py` — điểm kiểm soát **duy nhất**
  cho chuẩn hoá kết quả provider. Provider mới thêm vào sau này tự động tuân thủ.

### Fixed
- **Baseline `mypy --strict` bị lệch ngay từ đầu:** file ghi 556 dòng nhưng thực tế có
  **1266** lỗi strict, nên `check_mypy_baseline.py` luôn đỏ và gate không bảo vệ được gì.
  Đã reset về trạng thái thật kèm **hạn 30 ngày (2026-11-01)**, và hạn giờ **được thực thi
  thật**: quá hạn thì gate đỏ, buộc thu hẹp baseline hoặc xin gia hạn có lý do.
  Ưu tiên giảm dần: `common/data.py` (142), `broker/tcbs/account.py` (66),
  `explorer/vci/company.py` (56), `brokerage/tcbs/client.py` (36).
- **CI không chạy cho PR vào `dev`:** cả 4 workflow trigger `branches: [main, develop]` nhưng
  repo **không có branch `develop`** (`git rev-parse --verify develop` → `fatal`). Đã đổi
  thành `[main, dev]`.

### Changed
- **Retry policy rõ ràng hơn:** đường không-auto retry cả lời gọi provider (`DEFAULT_RETRIES=3`,
  như trước). Đường `AUTO` retry **từng provider** rồi mới xoay vòng — tránh việc hết pool
  bị thử lại N lần.
- Khi mọi provider đều lỗi, hệ thống **ném lỗi gốc** thay vì trả DataFrame rỗng (frame rỗng
  khiến người dùng tưởng "không có giao dịch" thay vì "đã lỗi mạng").
- Lỗi lập trình (`TypeError`…) **không** bị failover che giấu: ném thẳng ra.
- ⚠️ **BREAKING (giới hạn ở đường `Vnbroker`)**: `quote.history()` qua facade giờ trả
  `time` **tz-aware** `Asia/Ho_Chi_Minh` thay vì tz-naive, và lọc cắt theo `start`/`end`.
  - Lý do: provider khác nhau trả tz khác nhau (VCI tz-aware, KBS/DNSE/SSI tz-naive) khiến
    `pd.concat` sinh dtype `object`; VCI còn trả nến ngoài khoảng yêu cầu mà không báo lỗi.
  - Đây là tiền quyết cho failover tự động (GĐ3): xoay vòng provider giờ trả đúng schema.
  - Gọi provider trực tiếp (`VCIQuote(...).history()`) **không đổi hành vi**.
  - Code so sánh `df["time"]` với timestamp naive cần `.dt.tz_localize(None)`.

## [2026-09-23] — Release 3.4.0: SSI Swap Parity (P0–P4)

### Added
- **SSI swap parity**: `source="SSI"` dùng qua lại với KBS/VCI cho
  `quote.history` (mở `30m`, cửa sổ `HH:MM:SS`, `fetch_multiple` batch),
  `listing`, `trading.price_board` (`trading_date` + concurrent).
- **SSI T2 mới**: `explorer/ssi/{indices,securities,screener}.py`
  (index list/members/summary/history, securities summary/master/foreign-room,
  screener lọc local) + TTL phân tầng (symbols 6h, indexSummary 5m, master 60s).
- **SSI T3 realtime**: `explorer/ssi/live.py` (`intraday_ticks`,
  `depth_snapshot`, `session_snapshot`, `session_flags`) + `market.*`
  subscribe trong `SSIStreamManager`.
- **AUTO credential-aware**: SSI vào candidates quote/listing/trading khi có key
  (failover cuối), opt-in primary `vnbroker_SSI_AUTO_PRIMARY=1`;
  persist debounce (10 events/1s) + `flush_router_state()`.

### Fixed
- **Deadlock cold-start** `build_source_order` (`Lock` → `RLock`,
  `core/source_router.py`) — treo vĩnh viễn trên process tươi.
- `Trading.FALLBACK_MAP` trùng dòng làm mất SSI fallback; bổ sung map cho
  Quote/Listing (1 chiều SSI→KBS,VCI); `_call_with_fallback` bắt thêm
  `UnsupportedMethodError`; lazy-auth cho SSI company/finance/news.

### Testing
- 40 tests mới (parity 16 + indices/securities 8 + screener 6 + live 10 +
  router SSI/debounce 8 + fetch_multiple 3 + live-gated 7, mock-only);
  full `tests/unit`: 909 passed, 5 skipped (live-gated).

## [2026-09-22] — Release 3.3.0: Retail + Unified UI

### Added
- **Retail facade** (`vnbroker/common/retail.py` + `Vnbroker.retail()`):
  giá vàng SJC/BTMC, tỷ giá Vietcombank — validate fail-sớm, DataFrame đúng
  schema + `source`, RuntimeError prefix nguồn khi lỗi mạng, chặn print legacy.
- **Unified UI** (`vnbroker/ui/`): `Market/Reference/Fundamental/Retail`
  delegate mỏng về `common.data`, `show_api()/show_doc()` + snapshot test.
- **InstrumentType** (`str`-Enum lowercase) + dedup `get_asset_type`
  (`core/utils/parser.py` còn 1 định nghĩa; khóa bug ETF-8-ký-tự bằng test).
- **kwargs-filtering** ở `Quote.history/intraday/price_depth` theo signature
  provider (passthrough khi có `**kwargs`, luôn giữ `show_log`).
- Docs: `docs/RETAIL_USAGE.md`, `docs/ROADMAP_V33_PLAN.md`.

### Testing
- 53 tests mới (retail 19 + ui 11 + asset-type 16 + quote-kwargs 3 + snippets 4),
  Retail coverage 96%, UI 100%, mypy/ruff sạch scope mới.

## [2026-09-22] — Release 3.2.0: SSI broker lane (native FastConnect v3)

### Added
- **SSI broker lane đầy đủ, native, không dependency `ssi-sdk`**:
  `vnbroker/broker/ssi/` (auth, account, money, equity, market, portfolio,
  fco, stream, client + `_paths/_enums/_utils/_signing/_transport`).
  - Auth: market-only (không OTP), OTP, Smart OTP push (poll 202/401114), refresh.
  - Market data: OHLC 8 timeframe, index/board summary, securities info/summary,
    master data trần/sàn/TC (tự gom pages).
  - Brokerage: balance/positions equity + phái sinh, PPMMR full-columns,
    maxBuySell, sổ lệnh, portfolio snapshot (map tường minh sang engine).
  - Write ký RSA-SHA256 stdlib (nanoid idempotency), `dry_run=True` mặc định.
  - 7 lệnh điều kiện FCO (GTD/Stop/Stop-Limit/Trailing/Trailing-Limit/OCO/BullBear)
    + query vòng đời + order book.
  - Streaming WebSocket native (`websockets>=12.0`): trade/quote/room/put/oddlot/
    OHLCV + order/portfolio events, alias `subscribe_fco_order_status`.
- `SSIBrokerClient` đăng ký `BrokerRegistry` (`vn.broker(provider="ssi")`).
- `SSICredentialConfig` (`VNBROKER_BROKER_SSI_*`), mở rộng `Redactor` key SSI.
- Docs: `docs/SSI_USAGE_GUIDE.md`, `docs/SSI_INTEGRATION_PLAN.md`, `.env.example`.

### Changed
- `websockets>=11.0` → `>=12.0` (sync client chỉ có từ 12.0).
- `write_gate` ParamSpec-typed (giữ nguyên behavior, verified bởi suite TCBS).
- `camel_to_snake` có type hints; `from_dict` credentials typed `dict[str, Any]`.

### Testing
- 171 SSI unit tests mới (mocked), SSI coverage 93%, mypy --strict + ruff sạch.
- Live integration gated `vnbroker_RUN_LIVE_INTEGRATION=1` (manual, OTP người thật).

## [2026-06-22] — Release 3.1.1: Cleanup — Remove SSI/VNDirect brokerage scaffolds

### Breaking Changes
- **Xóa hoàn toàn SSI brokerage scaffold**: `vnbroker/broker/ssi/` (auth, account, equity, market, money, portfolio, client) — chưa triển khai thực tế.
- **Xóa hoàn toàn VNDirect brokerage scaffold**: `vnbroker/broker/vndirect/` (auth, account, equity, market, money, portfolio, client) — chưa triển khai thực tế.
- **BrokerRegistry**: Chỉ còn `TCBS` provider. SSI, VNDirect đã bị loại khỏi registry.

### Removed
- Toàn bộ thư mục `vnbroker/broker/ssi/` và `vnbroker/broker/vndirect/`.
- References SSI/VNDirect trong `README.md`, `CLAUDE.md`, `broker/__init__.py`.

### Changed
- `README.md`: Cập nhật bảng broker providers, xóa SSI.
- `CLAUDE.md`: Cập nhật cấu trúc thư mục broker, xóa SSI/VNDirect khỏi roadmap.
- `broker/__init__.py`: Chỉ export TCBS broker client.

## [2026-06-18] — Release 3.1.0: Cleanup — Remove MSN/FMP, restructure core

### Breaking Changes
- **Xóa hoàn toàn MSN explorer**: `vnbroker/explorer/msn/` (quote, listing, company, finance, news, trading, helper, const) — không có dữ liệu thật.
- **Xóa hoàn toàn FMP connector**: `vnbroker/connector/fmp/` (quote, config, const) — không có API key, không có module khác.
- **SUPPORTED_SOURCES thu hẹp**: Chỉ còn `KBS`, `VCI`, `TCBS`, `DNSE`. MSN, FMP, GATEWAY, AUTO đã bị loại.
- **Xóa `fx()`/`crypto()`/`world_index()` tests**: Các phương thức này chỉ hoạt động với MSN/FMP — đã bị xóa.
- **Xóa `msn_symbol_map`**: `Vnbroker` không còn property này.

### Removed
- Toàn bộ file rác: test scratch, benchmark artifacts, planning docs, caches, vninvest-sdk.
- Toàn bộ planning/audit docs: `ARCHITECTURE_REVIEW.md`, `BENCHMARK_COMPARISON_REPORT.md`, ...
- `_load_msn_const()` và `_CURRENCY_ID_MAP`/`_GLOBAL_INDICES`/`_CRYPTO_ID_MAP` khỏi `data.py`.
- `GATEWAY`, `MSN`, `FMP` khỏi `DataSource` enum, `DataSources` compat class, `core/settings.py`, `dispatch.py`, `source_router.py`, `user_agent.py`.
- 4 orphan test fixtures gây ERROR (`mock_vci_send_request`, `mock_response_factory`, `diverse_test_symbols`).
- `GatewayHttpClient`, `launcher.py`.

### Changed
- `TODO.md` được thay thế bằng phiên bản cập nhật, không còn tham chiếu vninvest-sdk.
- `README.md` cập nhật bảng nguồn dữ liệu, env vars không còn FMP.

### Testing
- **522 passed**, 9 skipped, 8 warnings — **0 failures, 0 errors** sau cleanup.

## [2026-06-18] — Release 3.0.0: Direct Provider Architecture (Loại bỏ PAT/Gateway)

### Breaking Changes
- **Loại bỏ hoàn toàn vninvest-sdk/PAT/Gateway**: `vnbroker` giờ đây hoạt động độc lập, không phụ thuộc vào PAT hay Gateway SaaS.
- **Xóa `GatewayHttpClient`**: File `vnbroker/core/utils/gateway_client.py` đã bị xóa.
- **Xóa Gateway adapters**: `GatewayQuoteAdapter`, `GatewayListingAdapter`, `GatewayTradingAdapter`, `GatewayCompanyAdapter`, `GatewayFinanceAdapter`, `GatewayNewsAdapter` đã bị xóa khỏi `vnbroker/common/data.py`.
- **Xóa PAT exceptions**: `AuthenticationError`, `AuthorizationError`, `QuotaExceededError`, `InvalidPATFormatError`, `GatewayUnavailableError`, `EmergencyQuotaExceededError` đã bị xóa khỏi `vnbroker/core/exceptions.py`.
- **Xóa deprecated wrappers**: Các lớp `_DeprecatedQuote`, `_DeprecatedCompany`, `_DeprecatedFinance`, `_DeprecatedListing`, `_DeprecatedTrading`, `_DeprecatedNews`, `_DeprecatedMarketSnapshot`, `_DeprecatedFund`, `_DeprecatedStream` đã bị xóa khỏi `vnbroker/__init__.py`.
- **SUPPORTED_SOURCES không còn `GATEWAY` và `AUTO`**: Tất cả component chỉ hỗ trợ các provider trực tiếp (`VCI`, `KBS`, `TCBS`, `DNSE`, `MSN`, `FMP`).

### Architecture Changes
- `Vnbroker.__init__()`: Bỏ `pat_key`, `gateway_url` parameters. Chỉ còn `symbol`, `source`, `show_log`.
- `source` mặc định từ `"AUTO"` → `"KBS"`.
- Không cần PAT key để sử dụng thư viện.

### Removed
- Xóa thư mục `Projects/vnbrokder/vninvest-sdk/` (stub empty).
- Xóa thư mục `.agents/`, `tmp/`, các file test root liên quan PAT/Gateway.
- Xóa `create_pat.py`, `create_valid_pat.py`.

### Documentation
- Cập nhật `README.md` phản ánh kiến trúc Direct Provider.
- Cập nhật `CHANGELOG.md`.
- Cập nhật `TODO_MIGRATION.md` → đánh dấu hoàn thành.

## [2026-06-17] — Release 2.0.0: Multi-Source Architecture & Private Brokerage Lane

### Architecture
- **Multi-Source Support**: Market data accessible via multiple providers (VCI, KBS, TCBS, DNSE, MSN, FMP) with automatic failover
- **Direct Provider Access**: Each provider (VCI, KBS, TCBS, DNSE, MSN, FMP) has own credentials and direct API access
- **Supported Sources**: `GATEWAY`, `AUTO`, `VCI`, `KBS`, `TCBS`, `DNSE`, `MSN`, `FMP` for market data components
- **Source Router**: AUTO source with VCI-first for quote/company/finance, KBS-first for trading, exponential backoff failover

### Private Brokerage Lane
- **TCBS Broker Client**: Full trading operations via direct TCBS iFlash OpenAPI v1.0.0:
  - Read: Profile, Balance, Purchasing Power, Cash, Margin, Holdings, Orders, Executions, Derivatives Positions/Orders/Cash
  - Write: Place/Modify/Cancel orders (dry_run=True default, idempotency via request_id)
  - Market Data: Ticker info, snaps, BSA, intraday, derivatives info (public endpoints)
  - Portfolio Engine: Snapshot, PnL, reconciliation (pure compute)
- **DNSE Broker Client**: Scaffolded (coming soon)
- **Security Model**: Zero-Knowledge — OTP, API Key/Secret, PIN never transit Gateway. Direct client → Broker API for minimal latency and maximum security.

### API Changes
- `Vnbroker.__init__()`: Added `pat_key`, `gateway_url` for Gateway mode; direct provider credentials via env vars
- `Vnbroker.stock()`: Supports `source` parameter for direct provider access (VCI, KBS, TCBS, DNSE, MSN, FMP)
- `Vnbroker.fx()`, `crypto()`, `world_index()`: Support MSN and FMP sources
- `Vnbroker.broker()`: New method returning `TCBSBrokerClient` for private brokerage
- `Quote.history()`: Removed MSN symbol mapping logic
- `Finance` class: Removed duplicate methods (`industry_peers`, `industry_benchmark`, `industry_rank`, `_extract_latest_metric_values`)
- `Screener`: Removed (was TCBS-direct only)

### Testing
- All 560 unit tests pass (12 skipped — pre-existing live API/env issues)

### Migration Guide
```python
# Gateway mode (requires PAT)
vn = Vnbroker(pat_key="vninvest_pat_your_token")
acb = vn.stock("ACB")  # Uses Gateway

# Direct provider mode (no PAT needed)
vn = Vnbroker()
acb = vn.stock("ACB", source="VCI")  # Direct VCI access
acb = vn.stock("ACB", source="DNSE")  # Direct DNSE access (requires DNSE_API_KEY + DNSE_API_SECRET)

# Broker Lane (direct API)
client = vn.broker(provider="tcbs", api_key="tcbs_openapi_key")
client.authenticate(otp="123456")
balance = client.get_balance("0123456789")
```

## [2026-04-18] — Release 1.0.2: Core API standardization and production hardening

### Added
- Standardized insider API surface and normalization path with `insider_deals` compatibility across providers.
- New financial snapshot API: `fundamental_snapshot` in the finance facade.
- New industry comparison APIs: `industry_peers`, `industry_benchmark`, `industry_rank`.
- Onboarding dry-run coverage for mock provider registration without core rewrite.
- New usage guide for the three core analytics groups:
  - `docs/FINANCE_INSIDER_INDUSTRY_USAGE_GUIDE.md`

### Changed
- Stabilized unit test behavior by gating live integration suites behind `vnbroker_RUN_LIVE_INTEGRATION=1` to avoid false negatives from upstream rate limits.
- Updated implementation and signoff documentation for production-ready handoff.

### Validation
- Full unit regression after release changes: **195 passed, 6 skipped**.

## [2026-04-13] — Upgrade Notice: GitHub-only Version Comparison Fix

### Fixed
- **Perpetual false upgrade notices**: `_check_version_updates()` previously compared package metadata version (`1.0.x`) against GitHub release tags (`3.x`), causing the upgrade notice to fire on every import.
- **Root cause**: `importlib.metadata.version("vnbroker")` returns the editable-install packaging version (`1.0.0`) which is unrelated to the upstream release line (`3.x`).
- **Solution**: Added `_get_current_github_channel_version()` which reads the highest version key from `VERSION_REQUIREMENTS`, `VERSION_NOTICES`, and `PYTHON_VERSION_SUPPORT` in `vnbroker/config.py` (currently `"3.4.0"`) as the source-of-truth for the installed codebase version. GitHub-only comparison is preserved (no PyPI fallback added).
- **Message cleanup**: Removed noisy `package metadata: 1.0.0` text from notice output. Display now shows `Current: 3.4.0 (Python 3.x (venv))`.

### Added
- `_get_current_github_channel_version()` — internal helper in `vnbroker/core/utils/upgrade.py`.
- `get_github_version_diagnostics()` — public debug helper returning a dict with `package`, `github_repo`, `package_metadata_version`, `current_github_channel_version`, `latest_github_release`.
- `tests/unit/core/test_upgrade_notice.py` — 4 regression tests locking the GitHub-only update notice behavior.

### Tagged
- Branch `core` tagged as `v3.4.0-core`.

## [2026-04-11] - Stock News API, Filtering, and Health Monitoring

### Added
- **Unified News facade** in `StockComponents`: `stock.news` now provides normalized multi-source news access for stock symbols.
- **New News adapter and providers**:
	- `vnbroker/api/news.py`
	- provider wrappers for `VCI`, `KBS`, `TCBS`
	- RSS providers for `RSS_CAFEF` and `RSS_VNECONOMY`
- **Normalization and dedup pipeline**:
	- `vnbroker/news/normalize.py` for canonical schema mapping
	- `vnbroker/news/dedup.py` for duplicate reduction
- **Criteria-based filtering API**:
	- `News.filter(...)` supports symbol, query text, source list, and time-range filters
	- `News.query(...)` convenience alias for text search
	- utility `vnbroker/news/filtering.py`
- **Source health observability for News**:
	- `vnbroker/core/source_router.get_source_health_snapshot("news")`

[Rest of changelog preserved...]