# Phản hồi chính thức của vnbroker cho VNBROKER-REQ-001..005

- **Ngày:** 2026-10-14 · **Từ:** vnbroker · **Gửi:** vninvest (PM/Tech Lead)
- **Văn bản được trả lời:** `vninvest/docs/REQUESTS_TO_VNBROKER_20261014.md`
- **Base:** `main @ fe76670` · **Branch:** `feat/vninvest-req-20261014` (chưa merge)
- **Căn cứ:** ADR-006 của vninvest (broker SSOT qua vnbroker)
- **Gate:** `pwsh -File scripts/check_all.ps1` — **exit 0**, đo tại main tree ở commit này

> Mọi khẳng định dưới đây đều có **lệnh tái lập được** hoặc có **test giữ nó**.
> Số liệu đo bằng script, không đếm mắt và không lấy từ tài liệu cũ.

## Tóm tắt một đoạn

Cả 5 REQ đều được xử lý, nhưng **không phải theo đúng hình thức REQ viết** — vì
ba AC gốc mô tả cơ chế mà nguồn sự thật không có, hoặc không khớp với code.
Cụ thể: REQ-002 yêu cầu "phân trang `get_executions` theo ngày" làm phương án
dự phòng, nhưng endpoint đó **không khai báo tham số truy vấn nào** trong spec
TCBS; REQ-001 nói "3 lane" trong khi `BrokerRegistry` chỉ đăng ký 2 và nói
"không cần credential" trong khi `DNSEClient` bắt buộc credential; REQ-005 giả
định vnbroker chưa có normalize, hoá ra đã có — và phần REQ-005 *thật sự* cần là
hai lỗi **ở phía vninvest**, đo được bằng cách chạy code. Ngoài phạm vi 5 REQ,
audit tìm thêm một lỗi làm `__version__` sai 3 bản, tệ hơn là nó nằm đúng trên
đường REQ-001 đi qua. Chi tiết từng REQ ở §2.

---

## 1. Bảng tổng hợp

| REQ | Yêu cầu gốc | Kết quả | Nội dung |
|:--|:--|:--|:--|
| **001** | `capabilities()` theo lane | **Đã làm, đã sửa 3 lỗi AC** | 3 lane · class-level · không credential · 18 method đã gỡ đánh dấu đúng 100% |
| **002** | TCBS order history nhiều ngày | **Văn bản, không code** | Path không có trong spec; phương án dự phòng của REQ không thi hành được; 2 lane khác đã có |
| **003a** | Khai báo watchlist `unsupported` | **Đã làm** | Cả 3 lane, có contract test quét `dir()` trên class thật |
| **003b** | CRUD watchlist chuẩn 3 lane | **Chưa làm — bị chặn** | Không provider nào có API; đã ghi roadmap + cảnh báo trùng tên |
| **004** | `MARKET_TYPES` + docstring + lỗi có mã | **Đã làm, mở rộng** | Thêm `ORDER_CATEGORIES`; chặn ở choke point; phủ 15 method DNSEClient |
| **005** | Hút normalize + `market_type` fallback | **Làm, thu hẹp** | `normalize_payload` công khai + `get_*_all_markets` có nhãn; 13 method `Trade` còn nợ |

Ngoài phạm vi: **F-01** — `vnbroker.__version__` trả **3.4.0** trong khi source
là **3.7.2**.

---

## 2. Từng REQ

### VNBROKER-REQ-001 — `capabilities()` theo lane · **Đã làm**

**API mới** — `vnbroker/broker/capabilities.py`, gọi qua `BrokerRegistry.capabilities(provider)`
hoặc trực tiếp `from vnbroker.broker import capabilities`:

```python
cap = BrokerRegistry.capabilities("tcbs")
cap["version"]        # "3.7.2"  — dùng để phát hiện cache cũ
cap["provider"]       # "tcbs"
cap["registered"]     # True      — có trong BrokerRegistry không
cap["methods"]["get_order_history"]
# {"supported": False, "reason_code": "PATH_REMOVED_NOT_IN_SPEC:/aion/v1/accounts/{accountNo}/orders/history"}
cap["features"]["watchlist"]
# {"supported": False, "reason_code": "PROVIDER_NO_API", "note": "..."}
```

Toàn bộ dict **JSON-serialisable** (`test_capability_is_json_serialisable`), nên
đi qua được IPC/cache mà phía tiêu thụ cần.

**Đo được** (`.venv\Scripts\python.exe -c "from vnbroker.broker import capabilities; ..."`):

| Lane | Method công khai | `supported: false` | `registered` |
|:--|--:|--:|:--|
| `tcbs` | 70 | **18** | True |
| `ssi` | 47 | 0 | True |
| `dnse` | 36 | 0 | **False** |

18 method đã gỡ = 5 (`broker/tcbs/equity.py:57-63`) + 13
(`broker/tcbs/account.py:63-77`). Danh sách **đọc thẳng từ `_REMOVED_PATHS`**
chứ không chép lại — chép lại là cách chắc chắn nhất để hai danh sách lệch nhau,
mà điều kiện nghiệm thu của REQ là *"đúng 100%"*.

**Ba lỗi trong AC gốc — đã sửa, mỗi cái có một test:**

| # | AC viết | Thực tế đo được | Sửa |
|:--|:--|:--|:--|
| 1 | *"gọi trên **3 lane**"* | `BrokerRegistry` chỉ đăng ký `tcbs`/`ssi`. `DNSEClient` không phải `BaseBrokerClient` nên không thể đăng ký mà không nói dối kiểu (`_providers: Dict[str, Type[BaseBrokerClient]]`) | Bảng lane phủ cả 3; thêm cờ `registered` để tách "có trong registry" khỏi "có dùng được". Nếu chỉ đọc registry thì `capabilities("dnse")` ném `KeyError` — chính lane mà vninvest đang retry mù lại hỏi không được. |
| 2 | *"gọi **không cần credential**"* | `DNSEClient.__init__` **bắt buộc** `api_key`, `api_secret` | Dựng ở **cấp class**, không instantiate. `test_capabilities_never_constructs_a_client` làm `__init__` của cả 3 class nổ rồi chứng minh danh mục method vẫn ra đủ. |
| 3 | *(không nói)* | `BaseBrokerClient` chỉ có **4** method công khai (`authenticate`, `close`, `get_account_balance`, `get_account_list`) | Danh mục lấy từ class cụ thể. Dựng từ lớp cơ sở sẽ làm mất 66/70 method của TCBS. |

**Một điểm REQ chưa nêu, đã xử lý:** `vnbroker/broker/__init__.py:46-57` nuốt
lỗi đăng ký bằng `except Exception: pass`, nên provider có thể vắng mặt mà không ai
biết. `capabilities()` tách hai khái niệm đó bằng cờ `registered` thay vì để người
đọc tự đoán.

---

### VNBROKER-REQ-002 — TCBS order history nhiều ngày · **Văn bản, không code**

REQ cho phép hai phương án và yêu cầu *"hoặc văn bản xác nhận path đã chết +
alternative"*. Đây là văn bản đó. Kết luận: **cả hai phương án trong REQ đều không
thi hành được trên lane TCBS**, và lý do đã được khóa bằng contract test.

**Sự thật 1 — path không có trong spec.** `/aion/v1/accounts/{accountNo}/orders/history`
vắng mặt trong `docs/references/openapi-v1.0.0.json` (spec ghim sha256
`7f97d27b…42bd4a`, do `scripts/verify_tcbs_coverage.py` kiểm mỗi lần chạy gate).

**Sự thật 2 — phương án dự phòng của REQ không làm được.** REQ đề xuất *"phân
trang `get_executions` theo ngày"*. Đo trên spec:

```
GET /aion/v1/accounts/{accountNo}/matching-details  ->  0 tham số query
```

Không `from`, không `to`, không `pageIndex`/`pageSize`. Endpoint đó **không có
tham số nào ngoài `accountNo`**, và `get_executions()` (`broker/tcbs/equity.py:219-261`)
cũng không nhận tham số ngày. Đây là AC đòi cơ chế mà hợp đồng không có (L-P06) —
nên **đổi AC**, không viết code rồi báo xong.

**Sự thật 3 — spec có endpoint nhận ngày, nhưng là dòng tiền.**
`/erebos/v2/digital/trans-hist-cashStatements` (`fromDate`, `toDate`, `pageSize`,
`pageIndex`, `transactionCode`) và `/erebos/v2/digital/margin-info` (`fromdate`,
`toDate`, `page`, `size`). Không cái nào là **lệnh**. Nói rõ ở đây vì nếu không,
đây chính là chỗ dễ bị đọc nhầm là lối thoát.

**Sự thật 4 — endpoint lệnh duy nhất có phân trang là in-day.**
`/khronos/v1/order/in-day` có `pageNo`/`pageSize`. Tên nói rõ phạm vi: chỉ trong
ngày.

**Bằng chứng chéo — đây mới là tin quan trọng nhất của REQ-002.** Hai lane còn
lại **đã có** lịch sử nhiều ngày, đo bằng `inspect.signature` trên class thật:

| Lane | Method | Ngày |
|:--|:--|:--|
| `ssi` | `SSIBrokerClient.get_order_history(account_no, from_date, to_date, raw)` | ✅ |
| `dnse` | `DNSEClient.get_order_history(account_no, market_type, from_date, to_date, page_size, page_index, ...)` | ✅ |
| `tcbs` | `get_order_history(...)` | ❌ `PATH_REMOVED_NOT_IN_SPEC` |

⇒ **Giới hạn là riêng của TCBS iFlash OpenAPI, không phải của vnbroker.** Nếu
vninvest cần đối soát lịch sử khớp ≥ 30 ngày, SSI và DNSE trả lời được ngay
bằng `capabilities()` mà không cần đoán.

**Giới hạn trung thực — KHÔNG kết luận "path đã chết trên server".** TCBS trả
`401` **trước** khi route, nên có token hợp lệ hay hỏng đều không phân biệt được
route có tồn tại hay không (L-R04). Môi trường SIT `openapisit.tcbs.com.vn` DNS
fail (đã đo trước đây) nên cũng không thay thế được. Cái đã chứng minh là *"không
có trong hai tài liệu chính thức"* — đúng bằng mức chắc chắn mà AC gốc cho phép.
**Probe server: CHƯA CHẠY, và không thể chạy với tài khoản hiện có.**

**Tái lập:** `pytest tests/contract/test_tcbs_order_history_contract.py` (7 test).

---

### VNBROKER-REQ-003 — Watchlist

**(a) Khai báo — ĐÃ LÀM.** `capabilities(p)["features"]["watchlist"]` trả
`supported: false` + `reason_code: "PROVIDER_NO_API"` cho cả 3 lane, kèm `note`.

Và không chỉ khai — **contract test quét `dir()` trên class thật**: không lane
nào được có method tên chứa `watchlist` mà lại khai `unsupported`. Nếu tương lai
provider thêm API mà quên cập nhật capability, test đỏ.

**Cảnh báo trùng tên — REQ chưa nêu, quan trọng cho bước (b).**
`vnbroker/explorer/tcbs/tcbs_compatibility.py:296` **đã có** một hàm tên
`get_watchlist(filters, size)`. Nó **không phải** watchlist của user:
- nó POST `/ligo/v1/watchlist/preview` và trả `searchData.pageContent` — tức là
  **kết quả của bộ lọc (screener preview)**;
- không có create/update/delete;
- và `except Exception: return []` ở `:318-321` — **fail-open trả rỗng im lặng**,
  đúng thứ REQ muốn diệt.

Nếu định nghĩa `get_watchlist/create/update/delete` "chuẩn 3 lane" mà không xử
lý việc này, tên sẽ đụng nhau giữa lane 1 và lane 2. Đã ghi cảnh báo vào `note`
của capability và vào roadmap.

**(b) CRUD — CHƯA LÀM, và đây là câu trả lời chứ không phải trễ hạn.** REQ tự
nêu *"Cấm reverse-engineer web private (R-W2)"*. Đo trên cả 3 lane: **0** method
watchlist nào. Không có API thì không có gì để nối, và viết CRUD lên một nền
chưa có là việc bịa. Đã ghi vào roadmap `CLAUDE.md` kèm điều kiện mở: chỉ mở
khi provider công bố API.

---

### VNBROKER-REQ-004 — `market_type` của DNSE · **Đã làm, mở rộng**

**API mới** — `vnbroker/connector/dnse/constants.py`:

```python
from vnbroker.connector.dnse.constants import MARKET_TYPES, ORDER_CATEGORIES
MARKET_TYPES     # frozenset({"STOCK", "DERIVATIVE"})
ORDER_CATEGORIES # frozenset({"NORMAL", "STOP", "OCO"})
```

**Hành vi khi sai** — đúng như REQ yêu cầu (*"nhận lỗi có mã, không phải response
rỗng im lặng"*):

```python
client.get_positions("0123456789", market_type="ALL")
# DNSEValidationError: marketType='ALL' không hợp lệ. Giá trị được hỗ trợ:
#   DERIVATIVE, STOCK. ...
# error_code == "INVALID_MARKET_TYPE"
```

Ném ra **trước khi có một byte nào đi ra** — test dùng chặn `requests.Session.request`
để chứng minh điều đó chứ không chỉ khẳng định exception.

**Tập giá trị ghim theo bằng chứng, không đoán.** Đếm bằng script trên toàn repo
(docs + code + notebook) cho đúng **hai** giá trị, không có giá trị thứ ba:

| Giá trị | Bằng chứng |
|:--|:--|
| `STOCK` | `docs/COMPARE_DNSE_SDK.md:16` — ví dụ của doc chính thức `client.post_order(market_type="STOCK", ...)`; `docs/PLAN_TIER1_ROUND2.md:29-33`; `docs/HANDOFF_DNSE_ROUND2_20261009.md:36` |
| `DERIVATIVE` | `docs/DERIVATIVES_API_RESEARCH.md:58,76` — `POST /accounts/orders?marketType=DERIVATIVE` |
| `NORMAL`/`STOP`/`OCO` | `docs/NORMALISATION_POLICY.md:146` (`orderCategory`) |

**Ba mở rộng so với REQ, đều có lý do:**

1. **Phủ 15 method công khai, không chỉ `get_positions`.** `market_type` là tham
   số bắt buộc ở **15** method công khai của `DNSEClient` (đếm bằng
   `inspect.signature`; tương ứng 15 method trong `services/`). Chỉ sửa
   `get_positions` thì 14 method còn lại vẫn fail-open. Contract test quét
   `inspect.signature` của **mọi** method công khai có `market_type`.
2. **Thêm `ORDER_CATEGORIES`.** Cùng bản chất, cùng chỗ, cùng kiểu lỗi — mà
   `orderCategory` sai cũng ra HTTP 200 + body rỗng.
3. **Chặn ở choke point `DNSEHttpClient.request()`**, không rải theo method —
   đúng lập luận mà write gate của chính repo này đã dùng
   (`core/http_client.py:31-42`: *"adding a guard per method reproduces that bug:
   one endpoint added is one hole"*).

**Một điều chỉnh thứ tự do chính test buộc ra (L-R02).** Bản đầu tôi đặt write
gate trước validation; test lộ ra rằng khi đó một caller chưa `enable_write()`
nhận `WRITE_NOT_ENABLED` và **không bao giờ biết `marketType` của mình sai** — lỗi
tham số bị che bởi lỗi quyền. Đã đảo: validation trước gate.

**⚠ Nợ chưa đóng — 12 method của `Trade`.** `connector/dnse/trade.py` có **12**
method nhận `market_type` (đếm bằng AST), gọi `requests.*` trực tiếp ở ~28 chỗ,
không qua `DNSEHttpClient` nên không được hưởng choke point. **Cố ý trì hoãn**:
file đó **1352 dòng**, vượt ngân sách 800, thêm nữa là vi phạm L-P03. Cần tách
file trước rồi mới thêm. Đã ghi vào roadmap. `MARKET_TYPES`/`ORDER_CATEGORIES`
dùng được ngay với `Trade` ngay bây giờ.

---

### VNBROKER-REQ-005 — Hút `vnbroker_dnse_compat` về vnbroker · **Đã làm, thu hẹp**

REQ giả định vnbroker **chưa có** normalize. Đo thì đã có:
`DNSEClient._to_dataframe` (`client.py:64-95`) xử list / dict-envelope / dict-phẳng.
Phần "normalize" của REQ vì vậy không cần viết mới — cần **làm công khai** và
**chặt hơn**.

Nhưng khi đọc kỹ file phía vninvest để trả lời, đo được **hai lỗi thật** — và cả
hai đều do thiếu API ở đây, không phải do lỗi của vnbroker:

**Lỗi 1 — `fetch_account_balance` luôn trả 0.**
`get_balances(raw=False)` trả `DataFrame`; code kiểm `isinstance(raw, list)` rồi
`isinstance(raw, dict)` — `DataFrame` không thuộc loại nào, nên rơi vào
`else: data = {}`. Chạy thật:

```
input : {"accounts":[{"accountNo":"123","cash":5000000}]}
output: {'cash': 0.0, 'stock_value': 0.0, 'debt': 0.0, 'net_equity': 0.0}
```

**Lỗi 2 — vòng retry là code chết.** `break` ngay sau lần gọi đầu tiên không raise.
Giá trị sai bị server trả HTTP 200 + body rỗng nên không raise. Chạy thật với
stub trả DataFrame rỗng:

```
market_type actually called: ['ALL']     # STOCK/EQUITY không bao giờ chạy
```

Nên "retry mù" mà REQ-004 mô tả **không bao giờ retry** — và vì không raise nên
cũng không báo lỗi, trả `[]` im lặng.

**Đã giao trong vnbroker:**

```python
# 1. Chuẩn hoá là hợp đồng công khai, một chỗ
DNSEClient.normalize_payload(payload, *, as_records=False)
#   nhận DataFrame / list[dict] / dict (kể cả envelope) / None
#   lỗi to_dict("records") để NỔI LÊN, không biến thành []

# 2. Đọc nhiều market: tường minh, có nhãn, fail-closed
client.get_positions_all_markets("0123456789")
client.get_order_history_all_markets("0123456789", "2026-01-01", "2026-01-31")
#   -> DataFrame có cột `market_type` trên MỌI dòng
#   -> hỏi TẤT CẢ market trong MARKET_TYPES, không phải thử tới khi hết cách
#   -> lỗi ở bất kỳ market nào nổi lên, KHÔNG trả bảng thiếu dữ liệu (L-R01)
```

Cột `market_type` tồn tại kể cả khi một market không có dòng nào, để kết quả không
mất dấu vết của việc nó đã được hỏi.

**Cố ý KHÔNG thêm "fallback" im lặng.** Một fallback nuốt lỗi chính là L-R01 ở
dạng đọc dữ liệu. REQ-005 được hiểu là *"đừng bắt caller tự đoán"*, và đó là điều
đã làm — bằng validate + nhãn + fail-closed, không bằng một vòng retry thứ hai.

**Đã tách `MultiMarketMixin`** ra `multi_market.py`. `client.py` trước khi thêm là
**707 dòng**; thêm 155 dòng sẽ thành **862 — vượt** ngân sách 800 (L-P03). Sau khi
tách: **713 dòng**. Cùng cách làm với `EquityWriteMixin` ở
`broker/tcbs/equity.py`.

> ⚠ Số dòng ở đây đếm bằng `len(text.splitlines())`. Lệnh
> `Get-Content f | Measure-Object -Line` của PowerShell **không đếm dòng rỗng**
> và cho số nhỏ hơn thật — chính tôi đã viết sai con số trong bản nháp đầu tiên
> của chính văn bản này theo cách đó. Đây là L-E01 xảy ra ngay trong lúc viết
> báo cáo: số đẹp, đo sai, và không ai bắt được nếu không chạy lại script.

---

## 3. Ngoài phạm vi 5 REQ — F-01: `__version__` sai 3 bản

`vnbroker/__init__.py:8-10` đọc version qua `importlib.metadata.version("vnbroker")`.
Cài **editable** thì `dist-info` không được đóng lại khi bump version trong
`pyproject.toml`. Đo trên máy này:

| | |
|:--|:--|
| `pyproject.toml` | **3.7.2** |
| `import path` | working tree (đúng) |
| `vnbroker.__version__` | **3.4.0** |

`scripts/check_version_sync.py` báo xanh vì nó chỉ grep *literal* trong pyproject /
README / CLAUDE.md / config.py / tests — **không chạm `importlib.metadata`**. Đúng
loại gate "xanh vì kiểm sai mặt phẳng".

**Vì sao nó chặn REQ-001:** REQ-001 yêu cầu `version` *"để client phát hiện cache
cũ"*. Nếu lấy từ `__version__` thì client nhận **3.4.0** và kết luận sai ngay mục
đích của nó. Đây là lý do đã làm F-01 **trước** REQ-001.

**Đã sửa:** gate giờ so `pyproject.toml` với metadata của bản cài. Chưa cài thì
**bỏ qua, không báo đỏ** — "không đo được" khác "đo ra sai" (L-E04). Thông điệp
lỗi kèm cách sửa.

Khi viết gate, phát hiện thêm một lỗi của chính nó: in tiếng Việt ra console cp1252
gây `UnicodeEncodeError`, **làm mất chính thông điệp cần đọc**. Đã ép
`stdout`/`stderr` UTF-8 `errors="replace"` trước khi in.

**Bằng chứng fail-before / pass-after:**

```
Trước : gate exit=1 — "pyproject=3.7.2 nhưng dist-info=3.4.0"
         6 test: 5 xanh, 1 đỏ
Sau   : __version__ = 3.7.2 · gate exit=0 · 6/6 xanh
```

---

## 4. Gate

`pwsh -File scripts/check_all.ps1` (không `-Quick`), đo tại main tree, commit này:

| Gate | Kết quả |
|:--|:--|
| `ruff-src` | PASS |
| `version-sync` | PASS — 3.7.2 (pyproject, README, CLAUDE.md, config.py, tests/, **dist metadata**) |
| `lessons` | PASS — 5 file · 24/40 lesson |
| `tcbs-coverage` | PASS — spec sha256 `7f97d27b…42bd4a` (khớp) |
| `tcbs-bodies` | PASS — lệch đã biết: 0 |
| `provider-consistency` | PASS |
| `mypy-baseline` | PASS — baseline 1266, now 1138, fixed 128 |
| `pytest-contract` | **117 passed** |
| `pytest-full` | **2177 passed, 26 skipped** |
| `ruff-tests-all` | KNOWN-RED — 13 lỗi có sẵn ở HEAD, không do thay đổi này |

**exit 0. Không gate nào thất bại.**

> **Không báo delta số test.** Không có baseline `pytest-full` đo *trước* thay
> đổi (lần chạy đầu dùng `-Quick` nên bỏ qua) — nên chỉ báo số đo tại commit này,
> không so với con số của một lần chạy khác (L-E07).

> **CI GitHub Actions: CHƯA CHẠY.** Job bị từ chối khởi động do billing. Lần chạy
> thành công cuối 2026-10-02. Badge CI không phải bằng chứng.

**Tái lập toàn bộ:**

```bash
pip install -e . --no-deps          # bắt buộc: gate version-sync sẽ đỏ nếu dist-info cũ
pwsh -File scripts/check_all.ps1
```

---

## 5. Việc phía vninvest còn lại

1. **Xoá `vnbroker_dnse_compat.py`.** Dùng
   `DNSEClient.normalize_payload(..., as_records=True)` cho phần chuẩn hoá và
   `get_positions_all_markets` / `get_order_history_all_markets` cho phần đọc nhiều
   market. **Xoá kèm test** — AC gốc ("xoá file, test DNSE xanh") không bắt được
   hai lỗi trên, vì xoá mà không có test chứng minh số liệu đúng thì chỉ là xoá
   triệu chứng. Test tối thiểu: balance với payload thật phải **không bằng 0**.
2. **Bỏ vòng retry `("ALL","STOCK","EQUITY")`.** `ALL` không phải giá trị hợp lệ
   và sẽ giờ bị chặn ngay với `INVALID_MARKET_TYPE`. Dùng `MARKET_TYPES` hoặc
   `get_*_all_markets`.
3. **Đọc `capabilities()` thay vì `try/except`.** Trước khi gọi một method, hỏi
   `methods[name]["supported"]`.
4. **Chuẩn bị cho breaking change:** `marketType`/`orderCategory` sai giờ ném
   `DNSEValidationError` thay vì trả HTTP 200 + body rỗng. Bất kỳ chỗ nào còn đang
   "thử lại cho đến khi hết cách" sẽ nhận lỗi ngay.
5. **Không cần tự phát triển watchlist.** Cả 3 lane đều `unsupported`; đã có khai
   báo để UI không hứa sai.

---

## 6. Việc vnbroker còn nợ (cần Owner quyết định)

| Nợ | Vì sao chưa làm |
|:--|:--|
| Watchlist CRUD (REQ-003b) | Không provider nào có API. REQ cấm reverse-engineer private (R-W2). Đã khai `unsupported` + roadmap. |
| Validate `market_type` ở 12 method của `Trade` | `trade.py` 1352 dòng, vượt ngân sách 800. Thêm nữa vi phạm L-P03. Cần tách file trước. |
| Ghim spec DNSE kèm sha256 | DNSE không có file OpenAPI commit trong repo (khác TCBS). Nên `MARKET_TYPES` là tập **đã tài liệu hoá**, không phải enum do server công bố. Ghim spec sẽ biến nó thành enum chính thức. |
| Bump version + tag | Breaking change ⇒ nên là 3.8.0. Bump version là quyết định của Owner; `CHANGELOG.md` ghi `Unreleased` cho tới khi đó. |
| Probe server cho REQ-002 | Không làm được: TCBS trả 401 trước routing, SIT DNS fail. Cần JWT/OTP hợp lệ **và** spec không còn là nguồn duy nhất. |

---

## 7. Sai lệch so với văn bản REQ — để không ai tưởng là bỏ sót

| # | REQ viết | Thực tế | Xử lý |
|:--|:--|:--|:--|
| 1 | `_REMOVED_PATHS` ở `broker/tcbs/equity.py:50-58` | Thật là **`:57-63`** | Trích dẫn lệch 7 dòng; đã dùng đường dẫn tương đối trong test để không lệch nữa |
| 2 | REQ-002: *"cung cấp alternative chính thật (vd phân trang `get_executions` theo ngày)"* | Endpoint không có tham số truy vấn nào | **Đổi AC** thành văn bản + bằng chứng chéo 2 lane |
| 3 | REQ-005: *"vnbroker cung cấp normalize"* | Đã có (`_to_dataframe`) | Làm công khai + chặt hơn, không viết lại |
| 4 | REQ-005: *"market_type fallback"* | Fallback nuốt lỗi là L-R01 | Không làm fallback im lặng; làm validate + nhãn + fail-closed |
| 5 | REQ-001: *"3 lane"* qua `BrokerRegistry` | Registry chỉ có 2 | Bảng lane phủ 3 + cờ `registered` |
| 6 | REQ-001: *"không cần credential"* | `DNSEClient` bắt buộc credential | Class-level, không instantiate |
| 7 | REQ-001: *"đúng 100% `_REMOVED_PATHS` hiện tại"* | Đúng, 18/18 | Danh sách đọc từ `_REMOVED_PATHS`, không chép lại |
| 8 | REQ-003: *"khi provider mở API, cung cấp CRUD chuẩn 3 lane"* | Chưa có provider nào có API | Chưa viết code; roadmap + cảnh báo trùng tên |
| 9 | Trích dẫn `docs/RESEARCH_WATCHLIST_BROKER_20261014.md` | **Không tồn tại** ở cây hiện tại của vninvest (chỉ ở branch `feat/multibroker-plan-research`) | Kết luận REQ-003 ở đây dựa trên đo trực tiếp trên code vnbroker, không dựa vào tài liệu đó |

---

## 8. Lessons đã áp dụng

`Lessons áp dụng: [L-E01, L-E02, L-E03, L-E05, L-E06, L-E07, L-R01, L-R02, L-R04, L-P01, L-P03, L-P04, L-P05, L-P06]`

Những chỗ bài học đã **thay đổi cách làm**, không phải chỉ được đọc:

| Lesson | Nơi nó đã can thiệp |
|:--|:--|
| **L-P06** | AC của REQ-002 đòi cơ chế không tồn tại → đổi AC thay vì viết code rồi báo xong. Cùng cơ chế với 3 lỗi AC của REQ-001. |
| **L-R01** | "marketType sai ⇒ HTTP 200 + body rỗng" chính là L-R01 ở dạng **đọc**. Quyết định: chặn trước, không thêm fallback im lặng. |
| **L-R02** | Bản đầu đặt write gate trước validation; test lộ ra lỗi tham số bị che bởi lỗi quyền → đảo thứ tự. |
| **L-R04** | Không viết "path đã chết trên server"; ghi rõ tầng nào chặn và vì sao không probe được. |
| **L-E01** | Mọi con số trong văn bản này đo bằng script/AST/`inspect` kèm lệnh tái lập. Tập `MARKET_TYPES` đếm trên toàn repo, không lấy từ tài liệu. |
| **L-E02** | Kết luận REQ-002 đọc spec **đã ghim sha256** trong repo, không đọc file ngoài repo. Ghi rõ DNSE chưa có spec ghim — nên `MARKET_TYPES` mới là tập đã tài liệu hoá. |
| **L-E04** | Gate mới bỏ qua khi chưa cài distribution, thay vì báo đỏ. |
| **L-E06** | Bằng chứng "không có byte nào đi ra" dùng chặn `requests.Session.request`, không assert hình thức. |
| **L-E07** | Không báo delta số test vì không có baseline cùng điều kiện. |
| **L-P03** | `client.py` sẽ thành 760/800 nếu không tách → tách `MultiMarketMixin`; `trade.py` 1233 dòng thì **không** chạm. |
| **L-P04** | `capabilities` được thêm vào `__all__` của `vnbroker/broker/__init__.py` — không để symbol mới không ai export. |
| **L-P05** | Đo lại gate bằng script thay vì tin con số của lần chạy trước; phát hiện 2 lỗi trong code mình vừa viết (`UnicodeEncodeError`, sai thứ tự gate/validate). |
