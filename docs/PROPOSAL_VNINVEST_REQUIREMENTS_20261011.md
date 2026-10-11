# ĐỀ XUẤT NÂNG CẤP `vnbroker` — Đặc tả công việc cho đội code thư viện

**Ngày:** 2026-10-11 · **Người lập:** TechLead phía `vninvest` (consumer) · **Người nhận:** đội phát triển `vnbroker`
**Repo:** `C:\Mujoco Projects\vnbroker` · phiên bản hiện tại `3.7.0` (`main` @ `662e2ef`)
**Trạng thái:** ĐỀ XUẤT. Chưa sửa dòng code nào ở repo `vnbroker` (`git status` sạch).

---

## 0. Vì sao tài liệu này tồn tại

`vnbroker` không chạy trên laptop của một lập trình viên. Nó chạy **trong tiến trình Django** của `vninvest`, dưới nhiều gunicorn worker, cộng Celery task, cộng đường đặt lệnh có tiền thật.

Điều đó đổi bản chất của "bug": trong thư viện nghiên cứu, `DataFrame` rỗng là chuyện nhỏ. Ở đây, `DataFrame` rỗng là **một ngày dữ liệu đóng lại vĩnh viễn trong DB**, và nó chỉ tới người biết đó là lỗi sau khi có người ra quyết định dựa trên nó.

Tài liệu này viết ra **những gì thư viện phải cam kết**, và **những việc phải làm** để giữ cam kết đó. Không phải phê bình code — là **đặc tả giao diện giữa thư viện và ứng dụng**.

---

## 1. Nguyên tắc bất di bất dịch

Năm nguyên tắc dưới đây là **tiền đề**, không thỏa hiệp. Mọi work package ở §5 đều phải phục vụ chúng.

| # | Nguyên tắc | Nghĩa là gì cụ thể |
|:--|:--|:--|
| **P-1** | **Rỗng phải là tiếng kêu, không phải câu trả lời** | Provider lỗi → **ném**. Không bao giờ trả `DataFrame` rỗng có cột, không bao giờ trả `{}`, không bao giờ log *"thành công"* khi không có gì. Phân biệt được *"hôm nay nghỉ"* với *"provider chết"* là **bắt buộc**, vì caller sẽ dựa vào nó để quyết định có retry hay không. |
| **P-2** | **Không bao giờ thay đổi hệ thống của host** | Không sửa `warnings.formatwarning`, không `simplefilter` toàn cục, không `handlers.clear()` của logger đã cấu hình, không `asyncio.run()` từ trong event loop. Thư viện chạy **bên trong** một app đã cấu hình xong. |
| **P-3** | **Cấu hình đọc lúc truy cập, không lúc import** | Host app set biến môi trường trong `settings.py`. Thư viện đọc `os.getenv` trong thân class ⇒ set sau import là vô hiệu, **không có cảnh báo**. Đây là loại bug chỉ lộ ra ở môi trường khác. |
| **P-4** | **Lỗi vĩnh viễn ≠ lỗi tạm thời** | 401/403/404/400 là câu trả lời cuối, không phải tín hiệu "xoay vòng". Trộn hai loại khiến failover đốt hết provider rồi vẫn hỏng. |
| **P-5** | **Đừng sửa cái đang đúng** | Mục §7 liệt kê những thứ đang làm tốt. Đừng đánh đổi. |

---

## 2. Hợp đồng thư viện phải đáp ứng

Đây là phần **bắt buộc** — mỗi dòng là một điều kiện nghiệm thu.

### H-1. Tín hiệu lỗi phải phân biệt được

| Yêu cầu | Lý do vninvest cần |
|:--|:--|
| Provider trả rỗng do lỗi → **ném `EmptyProviderResult`** | `vninvest_adapter.py` cần phân biệt "retry được" với "bỏ qua" để backfill không ghi rỗng vào DB |
| Lỗi mạng tạm / 429 → nỗi có `retry_after` | Celery task cần backoff đúng số giây server chỉ định |
| Lỗi vĩnh viễn (401/403/404) → **không** failover, **không** cooldown | Token hết hạn phải báo ra, không được quét hết pool rồi trả "hết provider" |
| Cột trả về phải **có schema khi có dữ liệu**, **không có cột khi lỗi** | Caller kiểm được "rỗng có cột" = nghi vấn ngay |

### H-2. Bất biến theo thời gian

| Yêu cầu | Lý do |
|:--|:--|
| Cùng input + cùng phiên bản ⇒ **cùng schema, cùng kiểu, cùng timezone** | Đây là chỗ 3.4.0 → 3.7.0 phá: `match_type` đổi casing, `time` đổi dtype. App không đổi dòng nào mà hành vi đổi. |
| **Mọi khung giờ phải là `Asia/Ho_Chi_Minh`**, không phải múi giờ máy host | Máy dev VN ra kết quả đúng, container `TZ=UTC` ra sai. Loại bug tái nhất vào CI. |
| Naive datetime trả về phải **ghi rõ là của múi giờ nào** | `vnbroker_adapter.py` đang hiểu sai chính vì thư viện không nói. |

### H-3. Bất biến theo môi trường

| Yêu cầu | Lý do |
|:--|:--|
| **Gunicorn N worker cho cùng kết quả** | `sqlite3.connect` mỗi lần flush, `_current_proxy_index` không lock, `asyncio.Lock` module-scope — mỗi thứ một kiểu hỏng khác nhau. |
| **Celery task chạy lặp lại cho cùng kết quả** | Mỗi task là một event loop mới. Đây là chỗ D-01 đóng băng đường async. |
| Cache key phải **phân biệt tenant/credential** | `DNSEListing` cache 24h với key sụp về tên lớn ⇒ kết quả của tài khoản A trả cho B. |
| Cache phải **trả bản sao**, không trả tham chiếu | `df['x'] = ...` của một request sẽ đổi dữ liệu 24h của request khác. |

### H-4. An toàn đặt lệnh (tiền thật)

| Yêu cầu | Lý do |
|:--|:--|
| **HTTP 200 ≠ đặt lệnh thành công.** Phải kiểm mã nghiệp vụ trong body | `error='0'` mới là thành công. `describe_business_code()` đã viết sẵn mà **không chỗ nào gọi**. |
| **Idempotency phải thật** | `IdempotencyStore` là code chết. `request_id` của TCBS validate xong rồi vứt. SSI tự sinh key mới mỗi lần ⇒ retry là 2 lệnh thật. |
| `dry_run` phải **keyword-only, default `True`, mọi method** | 5 method DNSE đang default `False`. Không phải bypass, nhưng mất một lớp. |
| **Không tự gửi lại write body** khi gặp challenge OTP | `_handle_otp_challenge` gửi lại `original_request.content`. |
| Số tài khoản phải validate định dạng | `_validate_account_no` chỉ kiểm rỗng, trong khi đi thẳng vào URL đặt lệnh. |

### H-5. Quan sát được từ ngoài

| Yêu cầu | Lý do |
|:--|:--|
| Host app đọc được: version, health từng provider, đếm lỗi theo mã | Không có thì sự cố chỉ biết được qua log thô. |
| Lỗi **không** phải `builtins.ConnectionError` khi không phải lỗi mạng | Không phân biệt được "provider chết" với "tôi gửi sai". |
| `ERROR_CODES` khai phải **thật sự phát ra** | `NETWORK_002`/`NETWORK_003` khai trong `exceptions.py:398` nhưng constructor không truyền ⇒ không bao giờ xuất hiện. |
| Log phải đi qua handler của host, có filter của thư viện | Hiện `get_logger` cưỡng chế handler + set DEBUG + chặn `propagate`. |

### H-6. Hợp đồng phiên bản

| Yêu cầu | Lý do |
|:--|:--|
| `__version__` đúng, từ metadata | Hiện `pyproject` = 3.7.0, metadata trong `.venv` = 3.5.0, `__version__` = 3.4.0. Logic so sánh phiên bản đang chạy trên **số sai**. |
| `VERSION_NOTICES` machine-readable (breaking change + ngày + SHA) | Để app assert lúc boot thay vì đọc changelog bằng mắt. |
| `MIN_VER` / `MAX_VER` | Chặn downgrade ngoài ý muốn. |
| Thêm `scripts/check_breaking_api.py` — diff AST public surface giữa 2 tag | 6 claim trong `CHANGELOG` kiểm chứng được: **2 đúng, 1 nửa vời, 2 dễ hiểu nhầm, 1 nghi sai**. Không ai đọc mà tin tuyệt đối. |

---

## 3. Danh sách bug theo mức độ

### 🔴 BLOCKER — mỗi cái một mình đủ để phá

| ID | Vị trí | Vấn đề | Hệ quả đo được |
|:--|:--|:--|:--|
| **BL-1** | `core/utils/async_client.py:57` + `:90` | `asyncio.Lock()` tạo ở **module scope** (`RATE_LIMITER` dòng 90). Gắn với event loop đầu tiên. | Đo: batch đầu **120/120 OK**; batch 2/3/4 **1/120 OK, 119 lỗi** `is bound to a different event loop`. Lock kẹt `[locked]`, **không có đường phục hồi**. Celery/ASGI = đường async chết **sau đúng một lần dùng**. |
| **BL-2** | `core/utils/cache.py:87-101` | `_instance_state` trả `None` khi instance giữ **một** thuộc tính không-terminal (pydantic `ProxyConfig`, `DNSEClient`, `SSIMarketService`) ⇒ **toàn bộ state bị vứt**, key sụp về tên lớn. | Đo: **mọi instance `VCIListing` dùng chung 1 key**; `show_log=True/False` cùng key; 2 instance **proxy khác nhau** cùng key. Với `DNSEListing` (`@cached_listing(ttl=86400)`) ⇒ **credential tenant A phục vụ tenant B trong 24h**. |
| **BL-3** | `core/utils/client.py:435` × `core/source_router.py:467` | Mọi status ≠ 200 (trừ 429) thành `builtins.ConnectionError`; `ConnectionError` ⊂ `OSError` ⇒ `should_failover` trả `True` **vô điều kiện** ở nhánh đầu. Bảng marker dòng 471-487 là **code chết** trên đường sync. | Đo: 204/206/301/**400**/**401**/**403**/**404**/422/500 → `should_failover=True` hết. Ngược lại lỗi parse/schema-drift thật → `False`. Token hết hạn ⇒ 401 ở mọi provider ⇒ đốt hết pool. |
| **BL-4** | `broker/tcbs/equity.py:_write_request`, `broker/ssi/equity.py:150`, `connector/dnse/trade.py:418` | **Không kiểm mã nghiệp vụ của response write.** HTTP 200 + lệnh bị từ chối ⇒ trả về như thành công. `describe_business_code()` tồn tại tại `_write_http.py:139` và **0 caller**. | SSI sai nghiệp vụ ⇒ `{"order_id": "", "status": ""}` **không exception**. DNSE ⇒ `return None`. Người dùng tin lệnh đã vào sàn. |
| **BL-5** | `broker/security/idempotency.py` (toàn bộ), `broker/tcbs/equity_orders.py:61`, `broker/ssi/equity.py:99` | `IdempotencyStore` **code chết** (chỉ test import). TCBS validate `request_id` rồi **không gửi, không lưu**. SSI tự sinh key **mới mỗi lần** khi caller không truyền. | Network timeout sau khi lệnh đã gửi → caller gọi lại → **2 lệnh thật**. Đây là đường double-submit mặc định. |
| **BL-6** | `explorer/kbs/listing.py:93-101`, `:146-153`; `explorer/kbs/trading.py:130-146` | Lỗi bị nuốt → `pd.DataFrame(columns=[...])` — **có cột** ⇒ `common/data.py:482` phân loại là kết quả dùng được ⇒ `record_success` ⇒ cache 24h. `trading.py` còn log *"Truy xuất thành công"* sau khi nhận 429. | Đo: KBS 500 ⇒ `(0, 2)` DataFrame, không exception, **router ghi thành công**, cache 24h. `MarketSnapshot` thay tên công ty bằng mã. Không phân biệt được *"thị trường đóng"* với *"KBS chết"*. |

### 🟠 MAJOR — âm thầm, hoặc sai quyết định hệ thống

| ID | Vị trí | Vấn đề |
|:--|:--|:--|
| MA-1 | `base.py:180-200` × `:216` + `source_router.py:301` | Một lệnh `history()` với pool 5 provider chết = **15 request HTTP** (3 retry × 5). Lần gọi kế tiếp vẫn **15** dù cả 5 đã cooldown — `ordered_pool = healthy or candidates` khiến cooldown **vô hiệu với lưu lượng**. Cooldown chỉ là công cụ quan sát, không phải công cụ bảo vệ. |
| MA-2 | `core/utils/async_client.py:272`, `:328` | 429 **vẫn bị retry** trên đường async (4 request), và `retry_after` **mất** ⇒ cooldown rơi về 5s đoán. Đường sync làm đúng (1 request, `retry_after=1.0`). **Hợp đồng 3.7.0 công bố sai ở một nửa đường đi.** |
| MA-3 | `core/utils/client.py:436` | `return response.json()` nằm trong `try`; `JSONDecodeError` ⊂ `RequestException` ⇒ **200 + body HTML** (WAF, trang bảo trì, schema drift) thành `ConnectionError` ⇒ đánh dấu provider khỏe là chết. |
| MA-4 | `core/utils/cache.py:400-410` | Không lock, không single-flight. Đo: 8 thread cùng key ⇒ **8 lần gọi provider**. Với `LISTING_CACHE_TTL=86400` và `all_symbols()` nặng, đây là burst ngay lúc worker khởi động. |
| MA-5 | `core/utils/cache.py:268` | Trả **cùng tham chiếu** DataFrame đã cache, không copy. Đo: caller sửa tại chỗ ⇒ mọi caller khác thấy giá trị đã sửa. |
| MA-6 | `common/data.py:903-946` | 9 method `Listing` có `@lru_cache` ⇒ cùng khuyết điểm aliasing (MA-5), **và** pin tối đa 9×128 = **1152 instance sống** trong worker. Cùng file đã **cố ý tránh** `@lru_cache` cho `Company`/`News`/`Finance` với comment *"would leak self"* — bỏ sót `Listing`. |
| MA-7 | `core/utils/upgrade.py:459`, `:170` | `warnings.formatwarning` bị gán lại ở **module scope** lúc import; `simplefilter("always", UserWarning)` chèn lên đầu `warnings.filters` toàn cục. Đo: warning của host app mất **filename, line, category**; filter của Django/pytest bị đè. **Thư viện sửa hệ thống của host** — vi phạm P-2. |
| MA-8 | `core/utils/logger.py:225-227`, `:254` | `hasHandlers()` đi **lên cây** ⇒ thấy handler của Django ⇒ `.clear()` handler của module. Set level **DEBUG** mặc định. Đo: log `vnbroker.*` **không đi qua** formatter của Django (mất request-id, tenant), phát ở DEBUG bất kể `DJANGO_LOG_LEVEL`. Ngược lại `bulk_router.py`, `registry.py`, `proxy_manager.py`, `env.py` dùng `logging.getLogger` thuần ⇒ **không có redaction**. |
| MA-9 | `core/utils/logger.py:248-251` | `SensitiveDataFilter` gắn **trên handler**, không tắt `propagate` ⇒ secret lọt qua handler root của app. Chính codebase biết cách làm đúng: `broker/security/audit.py:26` đặt `propagate = False`. |
| MA-10 | `config.py:26,34,46,50` | `os.getenv` trong thân class ⇒ đọc **đúng một lần lúc import**. Đo: đặt biến trước import = 7; đổi sau import = **vẫn 7**. Không cảnh báo. Vi phạm P-3. |
| MA-11 | `common/data.py:609-613` + `:652` | `history(symbol=X)` chỉ set thuộc tính, `_run_with_failover` gọi `_update_data_source()` **không argument** ⇒ `self.data_source` không nạp lại ⇒ **trả dữ liệu symbol khác**, im lặng. |
| MA-12 | `common/data.py:296-306` | `_load_fallback_provider` mutate `self.source` **không `try/finally`, không lock** ⇒ lỗi thì giữ sai tên provider ⇒ **ghi sai provenance vào DB**. |
| MA-13 | `core/utils/transform.py:157-167` | `clean_numeric_string` xoá `,` **trước** khi kiểm tra nó ⇒ nhánh decimal-comma là **dead code**. Đo: `'1,5'` → `'15'` (sai 10×), `'-3,75'` → `'-375'` (sai 100×). |
| MA-14 | `core/utils/lookback.py:190-196`, `explorer/kbs/quote.py:359`, `explorer/vci/quote.py:141` | `datetime.now()` theo **múi giờ máy host**. Vi phạm P-3 / H-2. |
| MA-15 | `core/utils/lookback.py:156-178` | Interval phút rơi vào **tỉ lệ ngày**; `ratio=0.006` là dead code (điều kiện mâu thuẫn). Đo: `1m/5m/15m/30m` đều cho cửa sổ **150 ngày** như `1D`. |
| MA-16 | `core/utils/transform.py:1043` | `resample` **bịa nến rỗng** cho khoảng không giao dịch, với `volume=0` — **không phải NaN** nên lọt mọi bộ lọc null ⇒ làm lệch mọi chỉ số volume-weighted. |
| MA-17 | `core/utils/transform.py:268-272` + `core/utils/normalizer.py:147` | `_MATCH_TYPE_MAP` không có `ATO`/`ATC` ⇒ thành `unknown`. Bản vá ở normalizer chạy **sau**, nên **dead code**. Đo: `['ATO','a']` → `['unknown','unknown']`. |
| MA-18 | `connector/dnse/trade.py:384-416` | `place_order` **không validate gì ngoài `side`**. Không `quantity>0`, không whitelist `orderType`, không kiểm định dạng account — **fail-open so với phần còn lại của thư viện**. `loanPackageId` luôn được gửi kể cả khi `None`. |
| MA-19 | `broker/tcbs/_equity_common.py:51-60` + `equity_orders.py:105,166`, `derivative_orders.py:124,203,297,361` | Không chặn `price==0` cho lệnh LO (SSI thì có). `int(price)` cắt cụt âm thầm trên 7 payload ⇒ `price=24.5` (người dùng tưởng nghìn) → `int()=24` ⇒ **lệnh sai giá 1000×**. |
| MA-20 | `broker/tcbs/auth.py:72-84`, `broker/ssi/auth.py:104-114`, `:148-158` | `begin_authenticating()` set cờ rồi **thả lock**, `_post_gaia` gọi mạng **ngoài lock**, `except` ⇒ `self._session.revoke()`. 2 thread ⇒ 2 lần tiêu OTP, và thread thất bại **xoá token tốt của thread thành công**. |
| MA-21 | `brokerage/tcbs/client.py:134-161` | `_handle_otp_challenge` tự gửi lại **write body**. Nếu lần đầu đã tới broker mà response bị mất ⇒ **lệnh thứ hai**. `_is_otp_challenge` match **substring** ⇒ mọi lỗi 401 có chữ "otp" cũng kích hoạt. |
| MA-22 | `brokerage/base.py:211` + `brokerage/tcbs/client.py:107-116`, `:281-284` | HMAC ký `{timestamp}{method}{path}{body}` — **`params` không nằm trong chữ ký**. `get_orders` đặt số tài khoản vào `params` ⇒ MITM đổi `account` mà chữ ký vẫn hợp lệ. Không nonce ⇒ replay được trong cửa sổ timestamp. |
| MA-23 | `core/utils/client.py:148,189-201` | Rate limiter **tắt mặc định** ở đường sync (`_rate_limiter = None`, opt-in); đường async bật 300 rpm nhưng **per-process** ⇒ 8 worker = **2400 rpm thật**. Bất đối xứng hoàn toàn. |
| MA-24 | `core/health_store.py:80-86`, `:108` + `source_router.py:59` | `sqlite3.connect` **mới mỗi lần flush**, và `record_success` gọi `_persist_state` **mọi lần thành công**. Đo: **419.81 µs/call** so với 2.17 µs in-memory. `default_db_path()` là **một file duy nhất** dùng chung mọi worker, mỗi worker một transaction WAL riêng. Dưới `--preload`, `_health_state` bị copy sang fork. |
| MA-25 | `core/utils/compat.py:57-71`, `:15` | `except (AttributeError, TypeError)` quanh `df.map(func)` **nuốt lỗi thật của `func`** ⇒ chạy lại lần 2 (side effect nhân đôi) rồi ném thông báo **sai hoàn toàn** (thiếu cả `map` lẫn `applymap`). Đo trên pandas 3.0.2: `func` chạy 2 lần, lỗi ném ra là compat. `compat.py:15` crash lúc import với version `"3.0.0rc0"`. |
| MA-26 | `base.py:165` | `filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}` ⇒ provider có `**kwargs` bị **bỏ toàn bộ** tham số, im lặng. Đường bulk (`bulk_router.py:43-53`) dùng chung `common.data._filter_kwargs` và làm **đúng**. Hai bản cùng ý định, khác hành vi. |
| MA-27 | `explorer/kbs/listing.py:123-128` | `symbols_by_exchange(self, lang='vi', get_all=False, show_log=False)` — tham số đầu là **`lang`**. Caller tự nhiên truyền `'HOSE'` ⇒ lọc sai, lỗi bị nuốt. |
| MA-28 | `explorer/vci/quote.py:198-205` | `int(end_time.timestamp())` trên datetime **naive** ⇒ phụ thuộc múi giờ host. **`start` không bao giờ được gửi** — chỉ `countBack` + `to` ⇒ `start='2020-01-01'` với `count_back=100` âm thầm trả **100 nến cuối**. |
| MA-29 | `api/quote.py:123-130`, `:177`, `:216` | `@retry` **không khai `retry=` predicate** ⇒ 429 bị retry 3 lần; thiếu `reraise` ⇒ ném `tenacity.RetryError` thay vì `RateLimitError`, nên `except ConnectionError` của host không bắt được. |
| MA-30 | `core/utils/async_client.py:406-409`, `:327` | `_record_failure` chỉ gọi **bên trong** `_send_with_retry`. Lỗi ở `get_client()`/`RATE_LIMITER` không đi qua đó ⇒ đo được `total_failed: 0, successful_requests: 160` trong khi **119/120 thất bại**. Dashboard báo sai. |
| MA-31 | `core/registry.py` vs `core/settings.py:79` | `core/settings.py` mô tả "centralized configuration" nhưng **không module nào import nó** ⇒ `get_timeout`/`set_timeout`/`get_config` là **API chết**. Host cấu hình nhầm chỗ sẽ không có tác dụng, không lỗi. |
| MA-32 | `core/utils/upgrade.py:105-107` + `config.py:85-87` | `VERSION_REQUIREMENTS["3.7.0"]` yêu cầu `vnii>=0.1.5` nhưng **`pyproject.toml` không khai `vnii`** ⇒ cài `pip install vnbroker` là thiếu, kiểm tra phụ thuộc **bỏ qua im lặng** (`except Exception: pass`). Đo: `vnii MISSING`. |

### 🟡 MINOR — chọn lọc

`exceptions.py:317-367` (`NETWORK_002/003` không bao giờ phát ra; `TimeoutError` che built-in nên `isinstance(..., OSError)` = False ⇒ retry set ở `base.py:232` không khớp) · `exceptions.py:380` (`DeprecationWarning` thực chất là `UserWarning` ⇒ host không che được) · `health_router.py:30-33` (mất `retry_after`) · `health_router.py:21,46` (không evict theo số provider) · `provider_pool.py:56-58` (dựng lại pool mỗi request) · `user_agent.py:234` (**18 UA khác trong 200 lần gọi** — fingerprint bot, phá keep-alive) · `user_agent.py:229` (dead code) · `connection_pool.py:36` (1 session cho **mọi tenant**) · `env.py:128` (`KeyError` bị che, mọi máy nhận "Local" qua ngoại lệ) · `env.py:53,58,76` (`print()` vào stdout) · `env.py`/`performance_profiles.py:98` (ghi thẳng `os.environ`) · `indicators.py:14,144,260` (`min_periods=1` ⇒ `sma_50` trên frame 10 dòng cho 10 giá trị) · `indicators.py:205,234,265` (`fillna` biến NaN thành giá trị hợp lệ trong khoảng) · `indicators.py:314` (copy 4× khuếch đại: 24 MB → 96 MB) · `bulk_router.py:150` (tạo mới `ThreadPoolExecutor` mỗi lần gọi) · `core/utils/client.py:51-66` vs `:423` (`safe_url` chỉ DNSE dùng) · `core/utils/cache.py:294` (O(n) evict — đo thấp hơn dự đoán) · `cache.py:145` (`repr()` DataFrame 5000 dòng = 16.5 ms **mỗi lần truy cập**) · `broker/tcbs/equity.py:400,470` (số tài khoản đầy đủ rò vào exception message) · `broker/tcbs/equity.py:430,494` (`resp.text[:200]` không qua Redactor) · `broker/tcbs/account.py:476` (`_validate_account_no` chỉ kiểm rỗng) · `broker/session.py:43` (`state` writable, bypass được `write_gate`) · `brokerage/guards.py:121` (`enable_write` không kiểm auth) · `connector/dnse/core/signature.py:11` (`%a`/`%b` phụ thuộc locale ⇒ chữ ký lệch trên máy nhiều ngôn ngữ) · `brokerage/base.py:313` (`asyncio.run` trong event loop ⇒ `RuntimeError`) · `broker/tcbs/equity.py:76` (`NotImplementedError` là tín hiệu lỗi lập trình, `except Exception` sẽ nuốt).

---

## 4. Bảng "claim ↔ thực tế" của chính repo

Đội code cần biết: `CHANGELOG.md` **không phải** nguồn đáng tin tuyệt đối.

| Claim | Kết luận kiểm chứng |
|:--|:--|
| `time` chuẩn hoá `[ns, Asia/Ho_Chi_Minh]` | ⚠ **Đúng trên 2/4 đường.** `Normalizer` chỉ chạy trong `common/data.py::Quote` + `api/quote.py::Quote`. Gọi `explorer.*.quote` trực tiếp — rất phổ biến — **không hề được chuẩn hoá**. Hai đường trả dtype khác nhau. |
| `TCBS_AUTH_TOKEN` đã sửa | ⚠ **Dễ hiểu nhầm.** `TCBS_AUTH_TOKEN` **vẫn là biến hỏng** (48 ký tự, server trả `401 validate.token.error` trên 4/4 endpoint), chỉ còn là fallback cuối. Biến **mới** `TCBS_JWT_TOKEN` mới hoạt động. Production chỉ set `TCBS_AUTH_TOKEN` ⇒ **không có gì được cải thiện**. |
| `market_cap` phóng đại 1000× đã sửa | ⚠ **Đúng cho KBS, nghi sai cho VCI.** `explorer/vci/trading.py:133` stamp `attrs['price_unit']='VND'` vô điều kiện. Nếu VCI trả nghìn ⇒ 3.7.0 lệch **1000× theo hướng ngược lại**. Chính changelog cũng ghi "chưa đối chiếu được". |
| 429 không retry | ⚠ Đúng đường sync, **sai đường async** (MA-2). |
| `match_type` chuẩn hoá `['ATC','Buy','Sell']` | ⚠ Tập giá trị thật là `{Buy, Sell, ATO, ATC, unknown}` — và `ATO`/`ATC` vẫn bị đổi thành `unknown` (MA-17). |
| Logger che token/OTP | ✅ Đúng. Nhưng filter đặt sai chỗ (MA-9) và không phủ mọi logger (MA-8). |
| CI kiểm chứng | ❌ **`config.py:143-145` tự ghi CI không chạy vì billing.** Không có gate nào chạy khi merge. Đây là **nguyên nhân gốc** của toàn bộ 6 claim sai. |

---

## 5. Work package — đề xuất cụ thể cho đội code

Mỗi WP có AC kiểm được bằng **đo**, không bằng đọc. Ưu tiên P0 = chặn sử dụng, P1 = chặn mở rộng, P2 = chất lượng.

---

### WP-01 · Chặn đường async sau một lần dùng — `asyncio.Lock` module scope 🔴 P0

**Sửa:** `core/utils/async_client.py:57`, `:90`, `:209`

Tạo `RATE_LIMITER` và `AsyncClientManager` theo event loop thay vì theo module. Cách đơn giản nhất: `weakref.WeakKeyDictionary` khóa theo `asyncio.get_running_loop()`, fallback `threading.Lock()` cho đường sync.

**AC:**
- [ ] `fetch_multiple_requests` chạy **4 batch liên tiếp, mỗi batch 120 request** ⇒ **4×120 OK**, `n_err=0` (đo được hiện tại: 120, 1, 1, 1)
- [ ] Test hồi quy tồn tại trong `tests/unit/core/` và chạy trong gate
- [ ] `core/utils/__init__.py:57` không còn import side-effect tạo lock
- [ ] `RATE_LIMITER` không còn là biến module-level

---

### WP-02 · Cache key không được sụp — `asyncio.Lock`… _`instance_state` fallback 🔴 P0

**Sửa:** `core/utils/cache.py:87-101`

Khi `_instance_state` không gấp được state, hiện trả `None` ⇒ key sụp về tên lớn. Sửa: **trả về token phân biệt được** dựa trên `type` + giá trị các field không-terminal; và decorator phải **từ chối cache** thay vì collide khi không phân biệt được.

**AC:**
- [ ] 2 instance `VCIListing` **proxy khác nhau** ⇒ **2 key khác nhau** (đo được hiện tại: `true` = collide)
- [ ] `show_log=True` vs `False` ⇒ **2 key khác nhau**
- [ ] `DNSEListing` / `SSIListing` sau khi `_market()` đã gán ⇒ key vẫn phân biệt
- [ ] Không trường hợp nào `cache key == tên lớn` khi instance có credential
- [ ] Test hồi quy cho từng provider: `vci`, `kbs`, `dnse`, `ssi`, `tcbs`

---

### WP-03 · Lỗi vĩnh viễn không được failover 🔴 P0

**Sửa:** `core/utils/client.py:411-435`, `core/source_router.py:463-487`

Tách `ProviderAuthError` / `ProviderNotFoundError` (401/403/404) và `ProviderBadRequestError` (400/422) khỏi lỗi tạm thời. `should_failover` phải trả `False` cho các loại đó **và không** `record_failure` (không cooldown).

Kèm: khi **mọi** provider đã cooldown, `source_router.py:301` phải **fail sớm** bằng lỗi rõ ràng thay vì quét lại cả pool (MA-1).

**AC:**
- [ ] Bảng đo hiện tại lật hết: 400/401/403/404/422 ⇒ `should_failover=False`
- [ ] 429 / 500 / timeout / DNS ⇒ `should_failover=True` **(giữ nguyên)**
- [ ] 200 + body không phải JSON ⇒ **không** đánh dấu provider chết (MA-3)
- [ ] 1 lệnh `history()` với pool 5 provider chết ⇒ **≤ 5 request** (đo được hiện tại: 15)
- [ ] Lần gọi kế tiếp trong cooldown ⇒ **0 request** provider đang cooldown
- [ ] `ValueError` từ schema drift vẫn nổi lên (giữ nguyên hành vi đúng hiện tại)

---

### WP-04 · Phân biệt "không có dữ liệu" với "provider lỗi" 🔴 P0

**Sửa:** `explorer/kbs/listing.py:93-101`, `:146-153`, `explorer/kbs/trading.py:130-146`, `explorer/vci/quote.py:277-278`, và rà toàn bộ `explorer/*`

Áp dụng **đầy đủ** `EmptyProviderResult` (đã có sẵn ở `common/data.py`) — hiện chỉ dùng ở `explorer/dnse/quote.py`.

- Provider lỗi → **ném**, không trả DataFrame rỗng có cột
- `explorer/kbs/trading.py` bỏ `logger.info("Truy xuất thành công")` vô điều kiện ở `:231-251`
- Mọi `return pd.DataFrame()` **sau một HTTP call** phải là chủ ý, có comment giải thích

**AC:**
- [ ] `_is_unusable_provider_result` (`common/data.py:482`) trả `True` cho frame rỗng **có cột** — hoặc bỏ khái niệm "có cột = khoẻ"
- [ ] `common/data.py:631-633` (docstring *"hết provider thì ném lỗi gốc, không bao giờ trả DataFrame rỗng"*) **thành sự thật** trên mọi provider
- [ ] Test: mô phỏng KBS 500 ⇒ ném, **không** ghi cache, **không** `record_success`
- [ ] Test: mô phỏng ngày nghỉ lễ (200, 0 dòng, có cột) ⇒ **vẫn** trả frame rỗng, **không** failover
- [ ] Không còn `logger.info` "thành công" nào đứng sau một nhánh lỗi

---

### WP-05 · Đặt lệnh: kiểm mã nghiệp vụ 🔴 P0 *(chỉ khi mở R3 live trading)*

**Sửa:** `broker/tcbs/equity.py:_write_request`, `broker/tcbs/condition_orders.py:_post`, `broker/tcbs/derivative_orders.py`, `broker/tcbs/money.py`, `broker/ssi/equity.py:150-155`, `broker/ssi/fco.py:372`, `connector/dnse/trade.py:418-422`

Gọi `describe_business_code()` (`_write_http.py:139` — **đã viết sẵn, 0 caller**) sau mỗi write. Thành công = `error=='0'` (TCBS) / `rc` (khronos) / `code` (physis) / `orderStatus` hợp lệ (SSI). Sai ⇒ ném exception riêng.

**AC:**
- [ ] Response `200` + `{"error": "X", "message": "..."}` ⇒ **ném `BrokerOrderError`**, không trả dict rỗng
- [ ] `describe_business_code` có **≥ 1 caller** thật ở đường write
- [ ] SSI `place_order` sai nghiệp vụ ⇒ raise, không trả `{"order_id": ""}`
- [ ] DNSE `place_order` non-200 ⇒ raise, không `return None`
- [ ] Test: 12/12 method write của TCBS có assertion mã nghiệp vụ

---

### WP-06 · Idempotency thật 🔴 P0 *(chỉ khi mở R3)*

**Sửa:** `broker/security/idempotency.py`, `broker/tcbs/equity_orders.py:61-65`, `broker/ssi/equity.py:99-102`

- **TCBS**: gắn `IdempotencyStore` thật vào `_gated_*`, có lock. Vì broker không có dedupe server-side, **dedupe phải ở client**.
- **SSI**: `request_id` **bắt buộc**. Xoá auto-generate, hoặc giữ nhưng **trả ra cho caller trước** khi gọi mạng.
- Thêm `enable_write()` cho `brokerage` phải kiểm auth (MA-`F-17`).

**AC:**
- [ ] Gọi `place_order` 2 lần cùng `request_id` ⇒ **1 lệnh**, lần 2 trả kết quả cache
- [ ] `IdempotencyStore` có caller ngoài test (grep `vnbroker/` khác `idempotency.py`)
- [ ] SSI: `place_order()` không truyền `request_id` ⇒ raise `BrokerValidationError`
- [ ] `brokerage/_handle_otp_challenge` **không** gửi lại body cho method không idempotent

---

### WP-07 · Đừng sửa hệ thống của host 🟠 P1

**Sửa:** `core/utils/upgrade.py:459`, `:170`, `core/utils/logger.py:225-227`, `:248-254`

- Xoá `warnings.formatwarning = ...` ở module scope → chuyển sang `warnings.showwarning` có phạm vi, hoặc chỉ khi `VNBROKER_CHECK_UPDATES=1`
- `simplefilter("always", UserWarning)` chỉ trong `warnings.catch_warnings()`
- `get_logger`: nếu logger đã có handler cấu hình ⇒ trả `logging.NullHandler()`, **không** `.clear()`; không ép level DEBUG
- `SensitiveDataFilter` gắn lên **logger** (qua `Logger.addFilter`) **và** `propagate=False` cho logger con — hoặc tốt hơn: export `redact()` cho host dùng

**AC:**
- [ ] `import vnbroker` **không** đổi `warnings.formatwarning`, `warnings.filters`, `logging.getLogger().handlers`, hay level của logger nào
- [ ] Warning của host app sau `import vnbroker` còn **filename + lineno + category**
- [ ] Filter `('error', UserWarning)` của host còn nguyên sau import
- [ ] Log `vnbroker.*` đi qua formatter của host (test với root handler giả)
- [ ] **Mọi** module của `vnbroker` dùng logger có redaction (hiện `bulk_router.py`, `registry.py`, `proxy_manager.py`, `env.py` không có)
- [ ] Test chạy trong một subprocess sạp để chứng minh không side-effect

---

### WP-08 · Cấu hình đọc lúc truy cập 🟠 P1

**Sửa:** `config.py:26,34,46,50`, `core/utils/upgrade.py:105-107`, `core/settings.py:79`

- `Config` đọc `os.getenv` qua `@property` thay vì class attribute
- `VERSION_REQUIREMENTS` kiểm dependency **thiếu thì báo**, không `except Exception: pass`
- `pyproject.toml` khai `vnii` nếu `config.py:85-87` yêu cầu nó — hoặc xoá khỏi requirements
- `core/settings.py` hoặc được dùng, hoặc bị xoá — **API chết là tài liệu sai**
- `performance_profiles.py:98` không ghi thẳng `os.environ`

**AC:**
- [ ] Đặt biến **sau** import ⇒ đọc được giá trị mới (đo được hiện tại: vẫn giữ giá trị cũ)
- [ ] Thiếu dependency bắt buộc ⇒ **báo**, không im lặng
- [ ] `vnbroker.__version__` == `importlib.metadata.version('vnbroker')` == `pyproject.toml` (đo được hiện tại: 3.4.0 / 3.5.0 / 3.7.0)
- [ ] Grep `vnbroker/` xác nhận `core.settings` có caller, hoặc file bị xoá

---

### WP-09 · Cache trả bản sao + chống stampede + bỏ `lru_cache` trên method 🟠 P1

**Sửa:** `core/utils/cache.py:268`, `:400-410`, `common/data.py:903-946`

- Trả `.copy()` cho DataFrame, hoặc ghi rõ contract "trả về là read-only"
- Single-flight: lock theo key, chỉ một thread gọi provider, các thread khác chờ
- Bỏ `@lru_cache` trên 9 method `Listing`; dùng `TTLCache` sẵn có, với **TTL** thay vì cache vô hạn
- Bỏ phân vùng theo `show_log` khỏi cache key (MA-N5)

**AC:**
- [ ] Caller sửa DataFrame trả về ⇒ lần gọi sau **không** thấy thay đổi (đo được hiện tại: thấy)
- [ ] 8 thread cùng key ⇒ **1** lần gọi provider (đo được hiện tại: 8)
- [ ] `common/data.py` không còn `@lru_cache` trên method instance
- [ ] `common/data.py` không còn giữ tham chiếu tới `self` trong cache dài hạn
- [ ] Cache value có **giới hạn bộ nhớ** đo được (dùng nhiều symbol trong worker dài)

---

### WP-10 · Đường async khớp hợp đồng của đường sync 🟠 P1

**Sửa:** `core/utils/async_client.py:272`, `:328`, `:406-409`, `health_router.py:30-33`

- 429 không retry ở async (khớp `base.py:231-233`)
- Giữ `retry_after` khi ném
- `_record_failure` gọi ở **worker**, không chỉ trong `_send_with_retry`
- `fetch_multiple_requests` trả **kiểu thống nhất** (luôn `DataFrame` + cột `error`, hoặc luôn dict có `ok`)
- `health_router.record_failure` truyền `retry_after` xuống `source_router`

**AC:**
- [ ] Server trả `429 + Retry-After: 1` ⇒ async đo **1 request**, `retry_after == 1.0` (đo được hiện tại: 4 request, `None`)
- [ ] `get_async_request_stats()` báo đúng số lỗi (đo được hiện tại: 0 lỗi khi thực tế 119)
- [ ] `throttled_responses` đếm **mỗi request logic**, không mỗi attempt
- [ ] Kiểu trả về đồng nhất trong mọi trường hợp, kể cả lỗi

---

### WP-11 · Bất biến thời gian & timezone 🟠 P1

**Sửa:** `core/utils/lookback.py:190-196`, `core/utils/transform.py:157-167`, `explorer/kbs/quote.py:359`, `explorer/vci/quote.py:141,198-205`, `core/utils/normalizer.py`

- `datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))` — **mọi** chỗ
- Sửa `clean_numeric_string`: kiểm `,` **trước** khi xoá
- `Normalizer` chạy ở **tầng explorer**, không chỉ `common`/`api` — hoặc ghi rõ contract "chỉ `Vnbroker.stock()` được chuẩn hoá"
- `_MATCH_TYPE_MAP` thêm `ATO`/`ATC`

**AC:**
- [ ] Cùng input cho **2 múi giờ host khác nhau** (`TZ=UTC` vs `TZ=Asia/Ho_Chi_Minh`) ⇒ **cùng cửa sổ ngày**
- [ ] `'1,5'` → `1.5`, `'-3,75'` → `-3.75`, `'12,345'` → `12345` (đo được hiện tại: `'15'`, `'-375'`)
- [ ] `explorer.{vci,kbs}.quote.history()` trả `datetime64[ns, Asia/Ho_Chi_Minh]` — **khớp** đường `Vnbroker.stock()`
- [ ] `['ATO','ATC','Buy','Sell','unknown']` đi qua `process_match_types` **giữ nguyên** ATO/ATC
- [ ] `'1m'` dùng `ratio` phút, không phải tỉ lệ ngày (đo được hiện tại: 150 ngày cho cả `1m` và `1D`)

---

### WP-12 · Đồng bộ hoá hai bản `_filter_kwargs` 🟠 P1

**Sửa:** `base.py:165` vs `bulk_router.py:43-53`

`base.py` bỏ toàn bộ kwargs khi provider có `**kwargs`; đường bulk làm đúng. Dùng **chung một** implementation.

**AC:**
- [ ] Provider có `def history(self, *args, **kwargs)` nhận **đủ** kwargs qua `base.py` (đo được hiện tại: nhận 0)
- [ ] Chỉ còn **một** định nghĩa `_filter_kwargs` trong repo

---

### WP-13 · Đặt lệnh: validate như các lane còn lại 🟠 P1 *(chỉ khi mở R3)*

**Sửa:** `connector/dnse/trade.py:384-416`, `broker/tcbs/_equity_common.py:51-60`, `equity_orders.py`, `derivative_orders.py`, `broker/tcbs/account.py:476`

- DNSE `place_order`: `quantity > 0`, whitelist `orderType`, kiểm định dạng account — copy `_validate_order_input` của TCBS
- TCBS: `LO` ⇒ `price > 0` (khớp SSI)
- Bỏ `int(price)` cắt cụt, hoặc validate tương thích nguyên
- `_validate_account_no` kiểm định dạng (docstring `money.py:535` đã ghi "10 chữ số")
- `dry_run` keyword-only + default `True` cho 5 method DNSE; mở rộng `test_write_safety.py::WRITE_METHODS`
- `session.state` thành read-only property

**AC:**
- [ ] `quantity=0`, `quantity=-1`, `orderType="FOOBAR"` ⇒ raise **trước** khi gọi mạng
- [ ] `LO` với `price=0` ⇒ raise trên **cả** TCBS và SSI
- [ ] `price=24500.7` ⇒ giữ nguyên độ chính xác hoặc raise rõ ràng (**đo**)
- [ ] 11/11 write method DNSE có `dry_run` keyword-only default `True`
- [ ] `session.state = X` từ ngoài ⇒ `AttributeError`

---

### WP-14 · Khóa luồng xác thực 🟠 P2

**Sửa:** `broker/tcbs/auth.py:72-84`, `broker/ssi/auth.py:104-114`, `:148-158`, `broker/session.py`

Giữ lock (hoặc `Condition`) quanh `begin_authenticating` → `_post_gaia` → `_store_token`. Chỉ `revoke()` nếu token thất bại **vẫn là** token mình đang thay.

**AC:**
- [ ] 2 thread gọi `authenticate()` đồng thời ⇒ **đúng 1** lần gọi network xác thực
- [ ] Thread thất bại **không** xoá token của thread thành công

---

### WP-15 · Gate phải bắt được thứ nó tưởng đang bắt 🟠 P2

**Sửa:** `scripts/check_tcbs_bodies.py`

4 lỗ hổng đã **kiểm chứng bằng thí nghiệm fail-before** trên bản sao (repo không bị sửa):

| Lỗ hổng | Gate báo |
|:--|:--|
| `payload.update({...})` (không phải `ast.Dict` literal) | `problems=0` — **im lặng** |
| Đổi HTTP verb `_post` → `_put` | `problems=0` — **im lặng** |
| `payload = dict(**locals())` | method **biến mất** khỏi danh sách mà `count` không tăng ⇒ gate **vẫn xanh** |
| Hoán đổi **giá trị** `quantity`/`price` | `problems=0` — **im lặng** |

Thêm: path không có trong spec bị **bỏ qua im lặng** (`scan():448-449`).

**Mở rộng cổng sang:** `broker/ssi/` (5 write method, ký RSA), `connector/dnse/trade.py` (9 method), `brokerage/tcbs/client.py` (3 method) — hiện **cổng payload cho SSI = 0**.

**AC:**
- [ ] Cả 4 thí nghiệm trên ⇒ gate exit ≠ 0
- [ ] Path không có trong spec ⇒ gate **báo**, không bỏ qua
- [ ] Mỗi write method của TCBS + SSI + DNSE đều có test fail-before/pass-sau
- [ ] Gate fail khi **không resolve được** payload, thay vì `continue`

---

### WP-16 · Hợp đồng phiên bản + gate breaking API 🟠 P1

**Sửa:** `vnbroker/__init__.py`, `config.py`, `pyproject.toml`, `scripts/`

- `__version__` đúng, 1 nguồn
- `VERSION_NOTICES` machine-readable: `[{version, date, sha, breaking: [...], data_contract: [...]}]`
- `MIN_VER` / `MAX_VER`
- `scripts/check_breaking_api.py`: diff AST public surface giữa 2 tag → fail CI khi symbol biến mất / signature đổi
- Ghi mức tin cậy cho từng claim trong `CHANGELOG.md`: **đã kiểm chứng trên server** vs **suy từ tài liệu**

**AC:**
- [ ] App assert được phiên bản lúc boot: `raise` nếu ngoài `[MIN_VER, MAX_VER]`
- [ ] Bump version ⇒ `check_breaking_api.py` liệt kê **chính xác** symbol đổi
- [ ] Xoá một public symbol trên bản sao ⇒ gate exit ≠ 0 (**fail-before test**)
- [ ] Mỗi entry `VERSION_NOTICES` có trường `verified_on_server: true|false`

---

### WP-17 · Trả tín hiệu nghiệp vụ về cho app 🟠 P1

**Sửa:** `core/health_store.py:80-86`, `source_router.py`, `exceptions.py:317-367`

- `sqlite3.connect` **tái dùng** thay vì mở mỗi lần (giữ hướng debounce hiện tại — đó là chỗ làm tốt)
- Đo lại sau khi sửa; mục tiêu **< 20 µs/call**
- `error_code` thật sự truyền cho `RateLimitError` / `TimeoutError` ⇒ `NETWORK_002`/`NETWORK_003` phát ra được
- Export API để host đọc: version, health từng provider, counter theo mã lỗi
- Cân nhắc `Retry-After` cooldown dùng chung giữa các worker (Redis) thay vì SQLite local

**AC:**
- [ ] `record_success` × 20 000 ⇒ **< 20 µs/call** (đo được hiện tại: 419.81 µs)
- [ ] `RateLimitError(...).error_code == 'NETWORK_002'`
- [ ] Host đọc được `vnbroker.health_snapshot()` mà không đụng internal

---

## 6. Thứ tự thực hiện

```
Hàng 1 — Chặn sử dụng (làm trước tiên, song song được)
  WP-01  async lock          ─┐
  WP-02  cache key           ─┼─ độc lập nhau, 3 người làm được
  WP-03  lỗi vĩnh viễn       ─┘
  WP-04  rỗng vs lỗi

Hàng 2 — Chặn mở rộng
  WP-07  đừng sửa host       ─┐
  WP-08  config lúc truy cập ─┼─ độc lập
  WP-09  cache copy/single-flight
  WP-10  async khớp sync     ─┘
  WP-12  _filter_kwargs
  WP-16  hợp đồng phiên bản

Hàng 3 — Chặn tiền (chỉ khi mở R3 live trading)
  WP-05  mã nghiệp vụ        ─┐
  WP-06  idempotency          ─┼─ **gộp 1 PR**: cùng chạm payload, tách khó
  WP-13  validate đặt lệnh   ─┘
  WP-14  khóa xác thực

Hàng 4 — Chất lượng & bền vững
  WP-11  timezone
  WP-15  gate payload
  WP-17  hiệu năng + tín hiệu về host
  + các MINOR ở §3
```

**Ràng buộc lịch:** `requirements.txt` của `vninvest` **đã ghim SHA của 3.4.0**. Không bump version pointer cho tới khi **Hàng 1 + Hàng 2 xong và có tag mới**. Việc bump SHA **không sửa được** bất kỳ bug nào ở §3 — nó chỉ chuyển sang code mới.

---

## 7. Những thứ đang làm tốt — đừng phá

| # | Thứ | Vì sao tốt |
|:--|:--|:--|
| 1 | Circuit breaker bán nguyên tử thật | `source_router.py:405-413` tăng `failures` + đặt `cooldown_until` trong **một** critical section. Tách ra là mất tính đúng. |
| 2 | Half-open probe | `is_half_open` + `probes` đưa lên đầu ⇒ **có đường hồi phục**, không kẹt vĩnh viễn. |
| 3 | `compute_cooldown_seconds` (`:363-388`) | Đọc `Retry-After` thật, `max` với suy đoán, kẹp `[1, 900]`, giữ trần 90s riêng, **giải thích lý do trong docstring**. Đo ra `5,10,20,40,80,90` và `86400 → 900` đúng như tài liệu. |
| 4 | `RateLimitError` kế thừa `ConnectionError` | Sửa đúng bài toàn cục thay vì vá `should_failover`. Giữ nguyên — nó giữ cho `except ConnectionError` của host vẫn chạy. |
| 5 | SSI không retry POST đặt lệnh | `_transport.py:35`, `:106-117`. Có test chứng minh bằng đếm session. Chuẩn nhất cả repo. |
| 6 | Cổng write DNSE nằm ở tầng HTTP, quyết định bằng **verb** | "Thêm endpoint mới là thêm lỗ hổng" không còn đúng. Có test chứng minh. |
| 7 | `guarded_write` kiểm chữ ký **lúc import** | `brokerage/guards.py:167-185`: thiếu `dry_run` ⇒ `TypeError` ngay lúc import, không phải lúc đặt lệnh. |
| 8 | `write_gate` trả envelope dry-run chỉ gọi *tên* kwarg nhạy cảm | `guards.py:66-72` — đúng bài học "đừng rò dữ liệu thật". |
| 9 | `check_tcbs_bodies.py` đọc payload bằng **AST** chứ không regex, có `--self-test`, exit **2** khi không verify được | Cổng chất lượng thật. Cần vá 4 lỗ hổng (WP-15), **không** nên bỏ. |
| 10 | Cache key encoding có ý thức adversarial | Length-prefix chống va chạm, type tag chống `1`/`True`/`1.0`, `blake2b` chống frame rộng, mask `<addr>` nhận ra hex uppercase. **Đừng viết lại đơn giản hơn** — chỉ sửa fallback của WP-02. |
| 11 | `_url_without_query` + `safe_url` | Bỏ query **tại nguồn** thay vì trông regex ở tầng log — đúng, vì DNSE/KBS ký HMAC trong query string. |
| 12 | `bulk_router` phân biệt lỗi lập trình / lỗi vận hành | `TypeError`/`AttributeError` nổi lên thay vì nuốt thành `logger.warning`. Nguyên tắc đúng — giữ khi sửa. |
| 13 | `is_token_expired()` fail-closed | `session.py:172-173` trả `True` khi chưa biết hạn. |
| 14 | Debounce persist | Thay fsync-per-request bằng flush mỗi 10 event / 1s. Hướng đúng; chỉ cần sửa `:81` (mở lại connection). |
| 15 | `parse_retry_after` **từ chối đoán** | Chỉ đọc `Retry-After` dạng giây, trả `None` cho HTTP-date thay vì bịa parser. |
| 16 | Log tiếng Việt có dấu | Là **chủ ý**. Nếu sửa encoding thì sửa ở tầng handler — **đừng** bỏ dấu khỏi message. |

---

## 8. Rủi ro khi sửa

| Rủi ro | Giảm thiểu bắt buộc |
|:--|:--|
| Sửa `should_failover` làm provider thật sự hỏng không được failover | Giữ nguyên 429/500/timeout/DNS. Test chỉ đổi 4xx/401/403. |
| Bỏ `@lru_cache` làm tăng tải provider | `TTLCache` có sẵn, phải cấu hình TTL **và** single-flight (WP-09) **cùng lúc**. |
| Bỏ `warnings.formatwarning` làm warning của thư viện kêu to | Chuyển sang `catch_warnings()` + `showwarning` có phạm vi. |
| `Config` thành property làm chậm hot path | Đo lại; nếu nóng thì cache theo `(env_name, generation)` thay vì đọc env mỗi lần. |
| Sửa `clean_numeric_string` làm đổi số của provider cũ | Chạy lại contract test của **mọi** provider trước khi merge. |
| EP-05/06 chỉ khi mở R3 nhưng tiêu chuẩn nâng version không kéo theo | Tách PR, ghi rõ **không** bật lane đặt lệnh trước khi EP-05+06 xong. |

---

## 9. Đề xuất quy trình

1. **Bật CI.** `config.py:143-145` tự ghi CI không chạy vì billing. Không có CI ⇒ không có gate nào chạy khi merge ⇒ **toàn bộ 6 claim sai trong §4 sẽ tái diễn**. Đây là việc số 1 về mặt quy trình, ngang với BL-1 về mặt kỹ thuật.
2. **Mọi work package kèm test fail-before/pass-sau.** Đo, không đọc. WP-15 đã minh hoạ: gate cũ báo xanh trên 4 kiểu lỗi.
3. **Mọi fix "im lặng" phải kèm chứng minh đo trước/sau.** Danh sách đo ở §3 chính là mẫu.
4. **`CHANGELOG.md` ghi mức tin cậy** cho từng claim.
5. **Đóng session bằng chạy toàn bộ gate**: `pwsh -File scripts/check_all.ps1` + `pytest tests/` — và **ghi "CHƯA CHẠY"** cho cái nào không chạy, không báo PASS suông.

---

## 10. CHƯA XÁC MINH — giới hạn của đề xuất

| Hạng mục | Vì sao chưa kết luận |
|:--|:--|
| TCBS có trả HTTP 200 + `error != "0"` thật không | Suy ra từ spec (`200.properties` chứa `error`) + docstring `equity_orders.py:71`. Cần JWT thật để probe. |
| `market_cap` VCI đúng hay sai đơn vị | Cần probe VCI thật. Chính changelog cũng ghi chưa đối chiếu được. |
| DNSE `nonce` trong chữ ký đúng chưa | `signature.py:36` không liệt kê `nonce` trong `headers=` dù `:41` thêm vào chuỗi ký. Cần đối chiếu tài liệu DNSE. |
| 18 method `NotImplementedError` còn sống trên server không | `client.py:23-24` tự thừa nhận *"CHƯA probe server"*. Nếu stop-limit còn sống, thư viện đang chặn nhầm. |
| `DNSEListing`/`SSIListing` có dùng đa-tenant không | WP-02 chỉ thành **sự cố rò dữ liệu** nếu mỗi user một credential. Không xác nhận được từ repo thư viện. |
| TCBS có echo `pinCode` trong body lỗi 400/422 không | Thiếu redaction là bất biến; **rò** thì chưa probe. |
| Test suite của repo | **CHƯA CHẠY** trong phiên audit này. Changelog tự ghi "1978 passed" cho 3.7.0 — **chưa tự kiểm chứng lại**. |

---

## 11. Câu hỏi cần đội `vnbroker` trả lời

| # | Câu hỏi | Vì sao chặn |
|:--|:--|:--|
| Q1 | `fetch_multiple_requests` / `async_send_request` có được gọi trong Django worker không? | Nếu có ⇒ BL-1 **đang xảy ra**, không phải rủi ro tương lai |
| Q2 | `DNSEListing`/`SSIListing` có dùng đa-tenant (mỗi user một credential) không? | Quyết định BL-2 là "cache sai" hay "rò dữ liệu" |
| Q3 | Rate limit định nghĩa theo tenant hay theo process? Có kế hoạch Redis token bucket? | MA-23 hiện bất đối xứng hoàn toàn |
| Q4 | `core/settings.py` giữ hay xoá? | API chết là tài liệu sai |
| Q5 | 18 method `NotImplementedError` có kế hoạch probe lại không? | Chặn nhầm chức năng còn sống |
| Q6 | CI có cứu được không hay sẽ bỏ vĩnh viễn? | Nếu bỏ thì §4 lặp lại mãi |
| Q7 | Ai chịu trách nhiệm bump version giữa 2 repo? | `vninvest` ghim SHA cứng; hiện không có hợp đồng |

---

*Bản nháp 1 — gửi đội code `vnbroker` để phản hồi Q1–Q7 trước khi chốt lịch.*
*Tài liệu liên quan: `vninvest/docs/AUDIT_VNBROKER_INTEGRATION_20261011.md` (bên consumer).*