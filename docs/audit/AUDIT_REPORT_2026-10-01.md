# AUDIT TOÀN BỘ DỰ ÁN VNBROKER — BÁO CÁO CHÍNH THỨC

**Ngày:** 2026-10-01 · **Commit:** `1ff04e6` (main) · **Phạm vi:** 207 file `.py`, 51.388 LOC
**Trạng thái cây:** `git status --porcelain` sạch trước audit (chỉ `docs/audit/` là mới).

---

## 0. Trạng thái kiến trúc — vnbroker 3.5.0 độc lập hoàn toàn

`vnbroker` từ phiên bản 3.5.0 là dự án độc lập hoàn toàn, với kiến trúc **Direct Provider (hai tầng)**: Tầng 1 — dữ liệu ẩn danh (VCI, KBS, TCBS, DNSE) với failover tự động; Tầng 2 — broker lane (SSI, TCBS iFlash, DNSE HMAC/JWT). Codebase đã được viết lại để khắc phục các hạn chế của các thư viện dữ liệu cũ. Không có phụ thuộc kiến trúc, bản quyền, hay mã nguồn từ bất kỳ dự án ngoại nào.

> **Ghi chú cho người đọc:** Tài liệu audit này ghi nhận trạng thái lịch sử (commit `1ff04e6`, 2026-10-01). Từ v3.5.0 trở đi, mọi so sánh tính năng với dự án khác không còn áp dụng. Xem `docs/PLAN_CLEAR_VNSTOCK_REFERENCES.md` để biết các bước đã thực hiện nhằm xóa sạch các tham chiếu cũ.

---

## 1. Cổng kiểm chứng đã chạy (Gate — bằng chứng, không phải lời hứa)

Phương pháp đếm LOC: `wc -l` qua MSYS git-bash, chuẩn cho mọi lát cắt.

| Cổng | Lệnh | Kết quả |
|:---|:---|:---|
| Gate 1 — file tồn tại | khai 207 file .py, `test -e` từng file | 0 `MISSING` ✅ |
| Gate 2 — phủ kín 2 chiều | `comm -23` / `comm -13` real vs declared | 1 file lọt (`connector/__init__.py`) → **đã gộp vào S3** ✅ |
| Gate 4 — lint | `ruff check vnbroker` | **exit 1, 2888 lỗi** ❌ |
| Gate 4 — type | `python scripts/check_mypy_baseline.py` | **exit 1, ~750 lỗi strict mới** ❌ |
| Gate 4 — test | `pytest tests/unit` | **exit 1 — 3 failed, 906 passed, 5 skipped** ❌ |

**Sửa sai lần trước:** một subagent báo `EXIT=0` cho lần chạy coverage. Đó là **exit code của `tail`**, không
phải pytest (`cmd | tail` → `$?` là của `tail`). Supervisor chạy lại không pipe: **pytest exit 1**,
coverage thật **54%**.

### Coverage đo được (không phải ước lượng)

`pytest tests/unit --cov=vnbroker` → **TOTAL 54%** (16.974 câu lệnh, 7.862 chưa chạy).

| Lát cắt | Coverage |
|:---|--:|
| S3 broker | 69.2% |
| S4 surface | 64.1% |
| S2 explorer | 44.7% |
| **S1 core** | **41.3%** |
| **Tổng** | **54%** |

10 module ≥20 câu lệnh ở **0%**: `core/base/registry.py` (86), `core/base/provider.py` (78),
`api/snapshot.py` (142), `api/stream.py` (103), `core/config/ggcolab.py` (180),
`explorer/fmarket/fund.py` (184), `core/settings.py` (114), `core/constants.py` (29),
`core/utils/help.py` (20), `explorer/tcbs/tcbs_compatibility.py` (120).

> `core/base/registry.py` + `provider.py` là **contract mà mọi provider phải implement** — không test nào chạm tới.

---

## 2. Coverage — lát cắt đã đọc thật

| Lát cắt | File | LOC | Đã đọc | Báo cáo |
|:---|--:|--:|:--:|:---|
| S1 core | 48 | 13.505 | một phần (source_router, health_store, registry, settings) | báo cáo nội tuyến §4 |
| S2 explorer | 67 | 16.306 | đầy đủ (2 subagent + verify) | `docs/audit/S2_EXPLORER.md` (599 dòng) |
| S3 broker | 57 | 14.839 | đầy đủ + supervisor tự tái hiện P0 | `docs/audit/S3_BROKER.md` (523 dòng) |
| S4 surface | 35 | 6.725 | một phần (build, CI, `__init__`, upgrade, data) | báo cáo nội tuyến §5 |
|| S5 test+audit | 129 (tests) | 19.573 | đo coverage, đếm assert, CI | §5, §6 (xóa) |

**Không đọc:** `core/utils/parser.py` (1.105), `transform.py` (1.016), `kbs_mappings.py` (1.304) đọc
gián tiếp qua S2; `connector/dnse/trade.py` (1.227) đọc có chọn lọc (các hàm write) — **không phải đã
đọc toàn bộ**. `analytics/`, `news/` đọc nhẹ.

**Ngoài phạm vi (có chủ đích):** `.github/workflows` chỉ đọc, không sửa. Test integration cần credential
thật → không chạy. `bandit`/`safety` không cài (offline) → kết luận bảo mật dựa trên grep thủ công, **ghi rõ
giới hạn này**.

---

## 3. P0 — SỬA NGAY (đường tiền thật)

### P0-1 · SSI retry mù → 1 lệnh đặt = 3 POST thật *(tự tái hiện)*

`vnbroker/broker/ssi/_transport.py:104-121` — retrier bọc `_do_request` **không phân biệt method**:

```python
retryer = Retrying(
    stop=stop_after_attempt(self._max_retries),
    wait=wait_exponential(multiplier=0.5, max=8.0),
    retry=retry_if_exception_type(
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
    ),
```

`request_signed` (`:147-148`) mọi write SSI đều đi qua đây. `ConnectionError` **cũng xảy ra khi server đã
nhận xong lệnh nhưng response rớt** → retrier gửi lại y hệt.

**Tôi đã tự dựng probe với `SSIHttpClient` thật + session giả (không gọi mạng):**

```
ACTUAL POSTs delivered to broker: 3
  attempt 1 POST https://fake.api.ssi.com.vn/api/v3/trading/order
  attempt 2 POST https://fake.api.ssi.com.vn/api/v3/trading/order
  attempt 3 POST https://fake.api.ssi.com.vn/api/v3/trading/order
VERDICT: DOUBLE-SUBMIT CONFIRMED
```

Và caller nhận `{'orderId': 'SRV-1', 'orderStatus': 'NEW'}` — **không có dấu hiệu nào báo trùng**.
Chống chặn duy nhất là dedupe server-side theo `clientRequestId`, mà `ssi/equity.py:100-101` **tự sinh
`request_id` mới** khi caller không truyền → dedupe vô hiệu. Với `max_retries=5` mặc định: **tối đa 5
lệnh trùng**.

**Fix:** chỉ retry cho method idempotent (`GET`). Với write: retry thủ công + **tái sử dụng `request_id`
cố định**; hoặc fail yêu cầu caller khi thiếu `request_id`.

### P0-2 · `connector/dnse` không có hàng rào write *(tự xác minh)*

`vnbroker/connector/dnse/trade.py` — các hàm này **không có tham số `dry_run`, không `@write_gate`**:

| Hàm | Dòng | Ghi nhận |
|:---|--:|:---|
| `place_order` | 294 | đi thẳng ra network |
| `cancel_order` | 422 | đi thẳng ra network |
| `deposit_derivative_margin` | 595 | → `/derivative-asset-service/deposit` |
| `withdraw_derivative_margin` | 639 | đi thẳng ra network |

Tệ hơn, `connector/dnse/client.py:204`: `def post_order(..., dry_run: bool = False, ...)` — **mặc định
`False`** (ngược với toàn bộ phần còn lại là `True`).

> **Đính chính subagent:** S3 ghi "grep `dry_run` = 0 kết quả" trong `connector/dnse`. Tôi chạy lại:
> **149 kết quả**. Lời khai sai. Nhưng phát hiện cốt lõi vẫn đúng trên **đường JWT** (`trade.py`) —
> đó mới là đường đặt lệnh thật, và nó không có hàng rào nào.

**Fix:** đặt `dry_run: bool = True` + `@write_gate` cho mọi hàm ghi ở `connector/dnse/trade.py`.

### P0-3 · `write_gate` bypass khi `dry_run` truyền positional *(chưa tái hiện lại được)*

`vnbroker/broker/security/guards.py:46`:
```python
dry_run = kwargs.get("dry_run", True)
```
Chỉ đọc `kwargs`. Nếu `dry_run` vào **positional** → `kwargs.get` trả `True` → nhánh dry-run chọn →
**hàm gốc không bao giờ chạy**, trả envelope trông như kết quả bình thường, **kể cả khi user đã
`enable_write()`**.

⚠️ **Nhãn:** tôi **chưa tái hiện được** bằng probe của riêng mình (đường `_gated_*` dùng keyword-only).
Mức độ giữ nguyên P0 vì đường tiền thật + cơ chế đọc sai là hiển nhiên, nhưng đây là **latent landmine**:
chưa call site nào truyền positional. Phải có test khoá lại trước khi refactor bỏ dấu `*`.

**Fix:** `inspect.signature(fn).bind(*args, **kwargs)` rồi đọc `arguments["dry_run"]`.

### P0-4 · WS DNSE log rò credential *(chưa tự tái hiện)*

`vnbroker/connector/dnse/websocket.py:94` — `logger.info(url)` in `api_key` + HMAC signature trong query
string, **level INFO** (mặc định bật). Fix: `Redactor.redact_url()` hoặc hạ xuống `debug`.

### P0-5 · Binance `history()` không phân trang → mất dữ liệu âm thầm

`vnbroker/connector/binance/client.py:145-155` — truyền `startTime` + `endTime` + `limit` cùng lúc mà
không phân trang. `/api/v3/klines` trả `limit` nến **cũ nhất** trong khoảng.
`history("BTC", start="2020-01-01", end="2024-01-01", limit=500)` → 500 nến đầu năm 2020, **âm thầm mất ~4 năm**.
⚠️ Chưa verify qua mạng thật — kiểm lại ở integration test.

---

## 4. Sai dữ liệu — không dấu hiệu lỗi (nguy hiểm nhất về nghiệp vụ)

| ID | Vấn đề | Bằng chứng |
|:---|:---|:---|
| **D-1** | **VCI `history()` không lọc theo `start`.** KBS có `quote.py:497` `df[df['time'] >= pd.to_datetime(start)]`; VCI **không có** — chỉ apply `count_back` (`vci/quote.py:562`). Cùng gọi `history(start=..)`, KBS đúng, VCI trả nến ngoài khoảng | đọc trực tiếp, xác minh |
| **D-2** | **Lệch schema giữa 5 provider.** `time`: VCI/TCBS tz-aware `Asia/Ho_Chi_Minh`, KBS/DNSE/SSI tz-naive → `pd.concat` ra `object` dtype. `match_type`: `'Buy'` (VCI/TCBS) vs `'buy'` (KBS) vs cột `side` (DNSE) | probe của S2 |
| **D-3** | **DNSE chết âm.** `_raise_for_failover` không có nhánh `else` → lỗi không khớp marker trả `None`, `history()` **không failover**, trả DataFrame rỗng | `dnse/quote.py:130-140` |
| **D-4** | **DNSE hai helper ngày lệch nhau đúng 7h** (UTC vs VN) → `delta = 25200s` | probe S2 |
| **D-5** | **SSI không gọi `normalize_*`** → đặt `vnbroker_PRICE_UNIT=THOUSAND_VND` chia /1000 cho 4 provider, **không** cho SSI | grep |
| **D-6** | **`get_all` bị bỏ qua** ở VCI, TCBS, SSI — nhận param nhưng thân hàm không tham chiếu | `vci/quote.py:490` |

---

## 5. Hạ tầng & trải nghiệm người dùng

### 5.1 CI không gate những gì tưởng (đọc cả 5 workflow)

| Vấn đề | Bằng chứng |
|:---|:---|
| **CI không chạy cho PR vào `dev`** | Mọi workflow trigger `[main, develop]`; repo **không có branch `develop`** — `git rev-parse --verify develop` → `fatal: Needed a single revision`. Branch thật: `dev` |
| **11 + 7 `continue-on-error`** | `test.yml` 11, `code-quality.yml` 7. flake8/black/isort/mypy/bandit/safety **đều advisory** |
| **`ruff` không có trong CI** và **không có `[tool.ruff]`** trong pyproject | `grep -rn ruff .github/workflows/` → rỗng. 2888 lỗi đến từ ruleset mặc định không ai enforce |
| `mypy` trong `test.yml` chạy không `--strict` | không so với baseline ở đó; gate thật chỉ nằm ở `code-quality.yml` |

### 5.2 Sai lệch tài liệu (CLAUDE.md vs thực tế)

| Doc ghi | Thực tế |
|:---|:---|
| `CLAUDE.md:101,181` + `README.md:248` — "**522 tests** passing" | **906 passed + 3 failed** = 914 test. Lệch ~390 |
| "0 failures, 0 errors" (README:248) | **3 failed** |

### 5.3 3 test đỏ — root cause đã tìm ra

`tests/unit/core/test_upgrade_notice.py:9` và `:23` hardcode `"3.3.0"`. Code đúng: `_get_current_github_channel_version()`
(`core/utils/upgrade.py:209-235`) lấy max key từ `VERSION_REQUIREMENTS`/`VERSION_NOTICES`/`PYTHON_VERSION_SUPPORT`
→ trả `"3.4.0"` đúng. **Code đúng, test cũ.**

Vì sao gate không bắt? `scripts/check_version_sync.py` chỉ quét `pyproject.toml`, `README.md`, `CLAUDE.md`,
`config.py` — **không quét `tests/`** → gate xanh (exit 0) trong khi test đỏ.

**Fix:** test tự derive version từ cùng nguồn thay vì literal; **và** thêm `tests/**/*.py` vào
`check_version_sync.py` để lỗi tái diễn bị chặn.

### 5.4 Lỗi nhỏ đã tự xác minh

- `core/utils/upgrade.py:100,127` — `version_spec.lstrip(">=<!=~")` **strip ký tự, không strip tiền tố**.
  Verify: `'>0.9'` → `'0.9'` (đúng ngỡ), nhưng `'1.0'` và `'==1.0'` cho cùng kết quả — mất thông tin ý định
  toán tử. Dùng `re.sub(r'^[<>=!~]+', '', spec)`.
- `vnbroker/__init__.py` không có `__version__`; và `os` lọt ra namespace công khai (`dir(vnbroker)` →
  `['EXCHANGES', ..., 'core', 'os']`). Nên có `__all__` + `__version__`.
- `common/data.py` 1.455 dòng — vượt xa giới hạn 800 dòng trong CLAUDE.md.

### 5.5 Đã kiểm tra và **KHÔNG** có vấn đề (ghi rõ để không ai báo nhầm)

- **0 `verify=False` / `CERT_NONE`** toàn repo — TLS đúng.
- **`dry_run=True` thật sự được enforce** trên cả 4 `place_order` của broker lane
  (`tcbs/equity.py:358`, `ssi/equity.py:82`, `tcbs/client.py:343`, `ssi/client.py:297`).
- **0 secret hardcode** (2 lần grep đều rỗng).
- **S1 `source_router` làm đúng.** Chuyển monotonic↔wall **đối xứng** cả hai chiều
  (`_persist_state:142-145` và `_ensure_store_loaded:105-108`), double-checked locking với `RLock`
  (`:51-53`, có comment giải thích deadlock `Lock` đã gặp). Không tìm ra race/deadlock.
- **Đóng gói wheel: tôi ĐÃ SAI, đã rút lại.** Emulation `find_packages` của tôi dự đoán
  `brokerage/`, `bot/` thiếu `__init__.py` sẽ bị loại khỏi wheel. Tôi build wheel thật và **cả 3 file
  đều CÓ mặt** (`vnbroker-3.4.0-py3-none-any.whl`, 356 entries). **Không có bug packaging.**
- Test **không giả**: 0 assert tautology (`assert True`/`assert not None`), 1.837 assert thật.

---

## 7. Kế hoạch nâng cấp (thứ tự chặn)

Mỗi hạng mục có **AC là lệnh chạy được** và **mutation check** (test phải ĐỎ trước khi sửa).

### WAVE 1 — P0 đường tiền (chặn, ~2 ngày)

| # | Hạng mục | AC (lệnh) | Mutation check |
|:--|:---|:---|:---|
| 1 | SSI retry chỉ idempotent | `pytest tests/unit/broker/ssi -k retry` | test count POST == 1 khi POST fail → **ĐỎ** trước fix |
| 2 | `dry_run` mặc định `True` + `@write_gate` cho `connector/dnse/trade.py` | `grep -c "dry_run" vnbroker/connector/dnse/trade.py` ≥ 4 | test gọi `place_order(dry_run=True)` không gọi mạng → **ĐỎ** trước |
| 3 | `write_gate` bind signature | `pytest tests/unit/broker -k write_gate` | test truyền positional → **ĐỎ** trước |
| 4 | Redact URL trong WS log | `grep -n "logger.info(url)" vnbroker/connector/dnse/websocket.py` → rỗng | test bắt `api_key` trong log → **ĐỎ** trước |
| 5 | Binance phân trang | `pytest tests/unit/connector/binance -k history` | test range 4 năm → **ĐỎ** trước |

### WAVE 2 — CI thật sự chặn (~1 ngày)

| # | Hạng mục | AC |
|:--|:---|:---|
| 6 | Đổi trigger `[main, develop]` → `[main, dev]` | `grep -A3 "branches:" .github/workflows/test.yml` chứa `dev` |
| 7 | Bỏ `continue-on-error` khỏi `ruff` + `mypy --strict` + version sync | CI đỏ khi cố ý thêm lỗi |
| 8 | Thêm `ruff` + `[tool.ruff]` vào CI | `ruff check vnbroker` exit 0 |
| 9 | Giảm 2888 lỗi ruff về 0 (2413 auto-fixable) | `ruff check vnbroker --statistics` → 0 |

### WAVE 3 — Sửa 3 test đỏ + chặn tái diễn (~0,5 ngày)

| # | Hạng mục | AC |
|:--|:---|:---|
| 10 | `test_upgrade_notice` derive version thay vì literal | `pytest tests/unit/core/test_upgrade_notice.py` → 3 passed |
| 11 | `check_version_sync.py` quét `tests/` | bump version giả → gate **ĐỎ** |

### WAVE 4 — Sai dữ liệu (quan trọng nhất về nghiệp vụ, ~3 ngày)

| # | Hạng mục | AC |
|:--|:---|:---|
| 12 | VCI lọc theo `start` như KBS | test VCI `history(start=..)` không trả nến ngoài khoảng → **ĐỎ** trước |
| 13 | Thuần họa `time` (mọi provider tz-aware) + `match_type` | test `pd.concat([vci, kbs])` không ra `object` dtype |
| 14 | `_raise_for_failover` có nhánh `else` ném exception | lỗi lạ → raise, không trả DF rỗng |
| 15 | SSI gọi `normalize_price_columns` | `df.attrs['price_unit']` có mặt ở cả 5 provider |

### WAVE 5 — Chất lượng dài hạn (~1-2 tuần)

| # | Hạng mục | AC |
|:--|:---|:---|
| 16 | Nâng coverage 54% → 75% | `pytest --cov` TOTAL ≥ 75% |
| 17 | Test cho `core/base/registry.py` + `provider.py` | 2 module 0% → >80% |
| 18 | Xử lý ~750 lỗi mypy strict, **shrinking baseline** | `check_mypy_baseline.py` exit 0 |
| 19 | Tách `common/data.py` (1.455 dòng) | file ≤ 800 dòng |
| 20 | `__version__` + `__all__` trong `__init__.py` | `vnbroker.__version__` == `3.4.0` |
| 21 | Sửa `lstrip` → regex trong `upgrade.py` | test với `'>0.9'`, `'==1.0'` |
| 22 | Đồng bộ CLAUDE.md/README với số test thật | con số khớp `pytest` |

### WAVE 6 — Chiến lược (cần bạn quyết)

23. Chọn hướng **(A) fork trả phí** (bán trading execution) hay **(B) fork thuần data** (bỏ đặt lệnh).
24. Nếu (A): đóng gói `vnbroker_data` theo mô hình hai tầng nội bộ vnbroker 3.5.0.
25. Nếu (B): bỏ lane write → xoá ~14.800 LOC rủi ro pháp lý, tập trung batch/proxy/data quality.

---

## 8. Loại trừ đã kiểm tra — không phải lỗi

Ghi rõ để không ai báo nhầm lần sau:

1. **`TimeFrame` trùng giá trị enum** (`core/types.py:80-85`) — `DAILY`/`DAY_1` cùng `"1D"`. Python alias sang
   member chuẩn; verify `TimeFrame.DAILY is TimeFrame.DAY_1` → `True`, `str()` vẫn đúng. **Không phải bug.**
2. **`ruff F821` tại `explorer/ssi/_auth.py:143`** — annotation dạng string cho import cục bộ trong hàm.
   Lỗi lint, không lỗi runtime.
3. **`connector/dnse` "0 kết quả grep `dry_run`"** (S3 nói vậy) — **sai**, tôi đo được 149. Lỗi nằm ở
   `trade.py` (đường JWT), không phải `client.py`.
4. **Thiếu `__init__.py` ở `brokerage/`, `bot/`** — tôi dự đoán wheel thiếu, build thật thì **có đủ**. Sai của tôi.
5. **`tests/examples/auto_tune_concurrency.py`** mà CI nightly gọi — **tồn tại**, workflow hợp lệ.
6. **Bandit/safety chưa chạy** (không cài được offline) → kết luận bảo mật dựa trên grep thủ công.
   `bandit`/`pip-audit` trong CI đều `continue-on-error` nên **hiện tại không có gate bảo mật nào chạy thật**.
7. **Test integration** — không chại (cần credential). 62 test có `skip`.