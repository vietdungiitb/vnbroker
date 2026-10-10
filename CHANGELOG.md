# Changelog

All notable changes to this project will be documented in this file.

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