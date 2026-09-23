# Kế hoạch v3.3 — Retail + Unified UI facade — Bản bàn giao cho đội code

> Trạng thái: **ĐÃ TRIỂN KHAI XONG (R0–R4) ngày 2026-09-22** —
> 53 tests mới, full suite 753 passed / 0 failure, Retail coverage 96%, UI 100%,
> mypy/ruff sạch scope mới. Bằng chứng: `artifacts/v33-handover/`.
> Trạng thái gốc khi lập plan: KẾ HOẠCH — CHƯA CODE.
> Cơ sở: vnstock v4 (Unified UI `Market/Reference/Fundamental/Retail`, `show_api`,
> `InstrumentType`, kwargs-filtering 4.0.4) — **chỉ học API shape, cấm copy code**
> (vnstock custom license). Bám code thật vnbroker v3.2.0.

## 0. Mục tiêu & phạm vi

### 0.1. Mục tiêu
1. Lộ `Retail` ra ngoài: `Vnbroker.retail()` → `gold(source="sjc"|"btmc")`,
   `exchange_rate()` — wiring lại `explorer/misc` sẵn có.
2. Unified UI mỏng `vnbroker/ui/` (`Market`, `Reference`, `Fundamental`, `Retail`)
   delegate về `common/data.py`, không rewrite data layer.
3. `InstrumentType` + `show_api()/show_doc()` + kwargs-filtering chống crash thừa param.

### 0.2. Scope IN
- `vnbroker/common/retail.py` (mới) + `Vnbroker.retail()` + `Vnbroker.gold()`? —
  **chốt:** chỉ `Vnbroker.retail()` (không thêm `gold()`/`exchange_rate()` trực tiếp
  trên Vnbroker để tránh phình API; `fx/crypto/world_index` giữ nguyên
  `NotImplementedError`).
- `vnbroker/ui/` (mới): `__init__.py`, `market.py`, `reference.py`,
  `fundamental.py`, `retail.py`, `registry.py` (cây API tĩnh cho `show_api`).
- `InstrumentType` (mới, `str, Enum`) + dedup `get_asset_type` trong
  `core/utils/parser.py` (đang trùng ở dòng 37 và 199).
- kwargs-filtering ở `Quote` (`common/data.py:368`) bằng `inspect.signature`.
- Docs: `docs/RETAIL_USAGE.md`, README/CHANGELOG/CLAUDE.md, `.env` không đổi
  (Retail không cần creds).

### 0.3. Scope OUT (cấm)
- Cấm sửa logic wire trong `explorer/misc/*.py` (giữ nguyên để không gãy hành vi cũ;
  validation + chuẩn hóa nằm ở facade mới). Ngoại lệ duy nhất: được thêm type hints
  nếu mypy bắt buộc (không đổi logic).
- Cấm copy code vnstock (`vnai`, `vnstock_ezchart`, MSN, sponsor-split).
- Cấm đổi signature public hiện có của `Quote/Company/Finance/Listing/Trading/News/Fund`
  (chỉ thêm, không sửa — trừ `get_asset_type` trả về vẫn so sánh được nhờ `str` mixin).
- Chưa làm P1–P3 SSI (explorer/router/cutover) và v3.4–v3.6 trong bản này.

## 1. Hiện trạng đã khảo sát (khóa)

| # | File | Thực trạng | Hệ quả cho plan |
|---|---|---|---|
| 1 | `explorer/misc/gold_price.py:8-74` | `sjc_gold_price(date)` POST SJC, `print` khi lỗi, trả `None` | Facade phải validate date trước + map `None` → DataFrame rỗng đúng schema |
| 2 | `explorer/misc/gold_price.py:77-112` | `btmc_goldprice(url=...key=3kd8...)` — key cứng trong default param | Giữ nguyên default (giống upstream), ghi rõ trong docs là key public của BTMC; cấm đưa key khác vào repo |
| 3 | `explorer/misc/exchange_rate.py:13-41` | `vcb_exchange_rate(date)` GET Vietcombank Excel-base64, `print` khi lỗi, date `''` = hôm nay | Facade chuẩn hóa `None/''` → hôm nay, fail-sớm date sai (hiện chỉ `print` rồi chạy tiếp với date sai!) |
| 4 | `core/utils/parser.py:37` + `:199` | `get_asset_type` định nghĩa 2 lần | Dedup về 1 implementation, giữ behavior bản đang được dùng (xác định bằng test trước khi xóa) |
| 5 | `common/data.py` | `Quote/Listing/Trading/Company/News/Finance/Screener/Fund` + `StockComponents` | UI delegate về các class này với source mặc định KBS; không đụng data layer |
| 6 | `common/client.py:128-186` | `fx/crypto/world_index` raise `NotImplementedError` | Giữ nguyên |
| 7 | Schema SJC hiện tại | `name/branch/buy_price/sell_price/date` | Chuẩn Retail giữ nguyên + thêm cột `source` |
| 8 | Schema BTMC hiện tại | `name/karat/gold_content/buy_price/sell_price/world_price/time` | Giữ nguyên + thêm `source`; không ép khớp SJC (ghi rõ khác biệt trong docs) |

## 2. API đích (chốt — implement đúng chữ ký)

```python
vn = Vnbroker()
retail = vn.retail()                                   # Retail (không tham số source)
sjc = retail.gold(source="sjc", date="2026-01-15")     # date None = hôm nay
btmc = retail.gold(source="btmc")                      # bỏ qua date
fx = retail.exchange_rate(date="2026-01-15")           # date None/'' = hôm nay

from vnbroker.ui import Market, Reference, Fundamental, Retail, show_api, show_doc
mkt = Market(source="KBS")                             # default KBS
hist = mkt.equity("SSI").history(start="2026-01-01")   # delegate Quote.history
ref = Reference(source="KBS")
prof = ref.company("SSI").profile()                    # delegate Company.profile
fa = Fundamental(source="KBS")
bs = fa.equity("SSI").balance_sheet(period="year")     # delegate Finance
show_api()  # in cây API; show_doc("Market.equity.history") in docstring

from vnbroker.core.utils.parser import get_asset_type  # trả InstrumentType (str-Enum)
get_asset_type("VNINDEX")        # InstrumentType.INDEX (== "index", lowercase như code hiện tại)
```

- `gold(source)`: source khác `sjc/btmc` → `ValueError` liệt kê hợp lệ; date sai
  format → `ValueError` (fail-sớm, thay vì `print` như misc hiện tại).
- Mọi read trả `pd.DataFrame` (rỗng đúng schema khi không có dữ liệu, **không `None`**);
  `df.attrs["source"] = "SJC"|"BTMC"|"VCB"`.
- `show_api()` in từ registry tĩnh (`ui/registry.py`), không inspect động
  (đơn giản, deterministic, test được bằng snapshot text).

## 3. Slices (DAG: R0 → R1 → R2 → R3 → R4)

### R0 — Retail facade + hardening I/O
- **Files:** `vnbroker/common/retail.py` (mới, `Retail` class), `common/client.py`
  (+`Vnbroker.retail()`), `tests/unit/common/test_retail.py` (mới),
  `tests/fixtures/retail/{sjc,btmc,vcb}.json` (mới, giá trị TEST_ rõ ràng).
- **Yêu cầu đạt:** validate date `YYYY-MM-DD` fail-sớm (kể cả `''` → hôm nay);
  SJC `date < 2016-01-02` → `ValueError`; `None` từ explorer → DataFrame rỗng
  đúng schema §1.7/1.8 + cột `source`; error paths **không `print`** (facade raise,
  test `capsys` assert stdout rỗng); BTMC bỏ qua `date` (documented).
  Ngữ nghĩa exception mạng (BTMC không try/except — `requests.get/json` ném thô):
  mọi exception từ explorer kể cả `requests.RequestException` → facade raise
  `RuntimeError` message rõ nguồn (`SJC:`/`BTMC:`/`VCB:` prefix) — KHÔNG nuốt thành
  DataFrame rỗng (để caller phân biệt "mạng lỗi" vs "API trả rỗng"); API trả rỗng
  (list rỗng/`success=False`) → DataFrame rỗng đúng schema. Test cả 2 nhánh.
- **Nghiệm thu + minh chứng:** `pytest tests/unit/common/test_retail.py -v`
  ≥18 cases (mock `requests.post/get` + `pd.read_excel`); coverage
  `vnbroker/common/retail.py` ≥90%
  (`--cov=vnbroker/common/retail --cov-report=term-missing`);
  `mypy --strict`, `ruff check/format` sạch scope mới.

### R1 — Unified UI mỏng
- **Files:** `vnbroker/ui/{__init__,market,reference,fundamental,retail,registry}.py`
  (mới), `tests/unit/ui/test_unified.py` (mới).
- **Yêu cầu đạt:** mỗi UI class chỉ delegate (không logic wire mới):
  `Market.equity(symbol)` → `Quote`, `Reference.company(symbol)` → `Company`,
  `Fundamental.equity(symbol)` → `Finance`, `Retail` → `common.retail.Retail`
  (UI method phải khớp 1-1 method thật của component — cấm phát minh thêm);
  `source` default `"KBS"`, sai source → `ValueError` của component gốc nổi lên
  nguyên vẹn; `show_api()` khớp snapshot trong `tests/fixtures/ui/api_tree.txt`
  (kèm cơ chế update snapshot: khi cây API cố ý đổi, chạy
  `pytest --update-snapshot`? — **chốt:** không flag tự động; sửa file snapshot
  bằng tay + ghi lý do vào commit message; test fail khi lệch).
- **Nghiệm thu + minh chứng:** tests mock ở tầng component (patch
  `vnbroker.common.data.Quote`…), assert delegate đúng args; snapshot `show_api()`
  khớp file; coverage `vnbroker/ui/` ≥85%.

### R2 — InstrumentType + dedup get_asset_type
- **Files:** `core/utils/parser.py` (sửa: 1 enum + gộp 2 hàm thành 1),
  `tests/unit/core/test_asset_type.py` (mới).
- **Yêu cầu đạt:** `class InstrumentType(str, Enum)` với **value lowercase khớp
  code hiện tại** (bắt buộc — repo có so sánh lowercase rải khắp
  explorer/company/finance/connector, UPPERCASE sẽ vỡ):
  `STOCK="stock"`, `INDEX="index"`, `DERIVATIVE="derivative"`, `BOND="bond"`,
  `COVERED_WARRANT="coveredWarr"` — đúng 5 giá trị hàm hiện trả về, cấm thêm
  member (`ETF/FUND/…` không bao giờ được trả; ETF 3 ký tự → `stock`, ETF 8 ký tự
  như FUESSVFL → `coveredWarr` là bug hiện hữu — **khóa lại bằng test, không sửa
  trong R2**, fix riêng ở phase sau). Nhờ `str`-Enum,
  `InstrumentType.INDEX == "index"` vẫn `True`.
  `get_asset_type` trả `InstrumentType`; trước khi xóa bản trùng
  (`parser.py:37` vs `:199`, body giống hệt, runtime binding là bản `:199`):
  viết test khóa behavior cả 2 (import trực tiếp từng bản qua reload module),
  giữ logic bản `:199`.
- **Nghiệm thu + minh chứng:** ≥15 cases gồm giá trị lowercase tường minh
  (`"index"`, `"stock"`, `"derivative"`, `"bond"`, `"coveredWarr"`) + case ETF
  8 ký tự khóa bug hiện hữu + mã lạ raise `ValueError`; full suite cũ xanh;
  mypy strict sạch.

### R3 — kwargs-filtering ở Quote
- **Files:** `common/data.py` (sửa `Quote.history/intraday/price_depth`),
  `tests/unit/common/test_quote_kwargs.py` (mới).
- **Yêu cầu đạt:** dùng `inspect.signature` của provider method để lọc kwargs lạ
  trước khi gọi (pattern vnstock 4.0.4); kwargs lạ → bỏ qua + `logger.debug`
  (không raise, không crash); kwargs hợp lệ đi qua nguyên vẹn (test spy assert).
  2 quy tắc đã xác minh trên code thật (bắt buộc):
  (a) **luôn giữ `show_log`** — là tham số chung của provider
  (kbs/vci/tcbs/dnse quote đều có), cấm filter mất;
  (b) nếu signature provider có `VAR_KEYWORD` (`**kwargs` — đã xác minh DNSE
  `history/intraday/price_depth` có, KBS/VCI/TCBS không) → passthrough toàn bộ,
  không filter. Áp dụng cho cả 3 method `history/intraday/price_depth`.
- **Nghiệm thu + minh chứng:** test provider fake signature hẹp (lọc),
  fake có `VAR_KEYWORD` (passthrough), fake thiếu `show_log` trong kwargs
  (vẫn truyền `show_log` mặc định); regression: các test Quote hiện tại vẫn xanh.

### R4 — Docs + release v3.3
- **Files:** `docs/RETAIL_USAGE.md` (3 snippets chạy được: SJC/BTMC/VCB),
  `tests/unit/examples/test_retail_docs_snippets.py` (mock, mirror chuẩn SSI),
  `README.md` (mục Retail + Unified UI), `CHANGELOG.md` (entry 3.3.0),
  `CLAUDE.md` (sơ đồ `ui/` + `common/retail.py`), bump `pyproject` 3.2.0→3.3.0.
- **Yêu cầu đạt:** snippet docs xanh trên mock; docs ghi rõ khác biệt schema
  SJC vs BTMC + key BTMC public có sẵn; không secret/placeholder gây nhầm.
- **Nghiệm thu + minh chứng:** full `pytest tests/unit` 0 failure (baseline 700);
  `artifacts/v33-handover/` đủ 6 file như chuẩn SSI
  (`pytest-unit/coverage/mypy/ruff/security-audit/release-notes.txt`).

## 4. Lệnh verify chuẩn (mọi slice)

```bash
python -m pytest tests/unit/common/test_retail.py tests/unit/ui/ -q -p no:cacheprovider
python -m pytest tests/unit -q -p no:cacheprovider
python -m mypy vnbroker/common/retail.py vnbroker/ui/ --strict --follow-imports=silent
python -m ruff check vnbroker/common/retail.py vnbroker/ui/ tests/unit/common/test_retail.py tests/unit/ui/
python -m ruff format --check vnbroker/common/retail.py vnbroker/ui/ tests/unit/common/test_retail.py tests/unit/ui/
# Đo coverage (bắt buộc dùng coverage run: pytest-cov --cov= path-form không thu
# được dữ liệu với module đơn lẻ trong setup repo này):
python -m coverage run -m pytest tests/unit/common/test_retail.py tests/unit/ui/ -p no:cacheprovider -q
python -m coverage report --include="*/common/retail.py,*/ui/*.py"
```

## 5. Rủi ro & giả định
1. Upstream SJC/VCB/BTMC đổi format không báo trước → facade chỉ chuẩn hóa,
   không hardcode parse sâu hơn hiện tại; test mock theo format đã khảo sát (§1).
2. BTMC key public trong default param là của upstream (giữ nguyên như vnstock);
   cấm thêm key riêng vào repo.
3. `print` trong `explorer/misc` giữ nguyên có chủ ý (Scope OUT) — facade đảm bảo
   nhánh lỗi được chặn trước khi tới đó; nếu phát hiện `print` lọt ra ở test
   `capsys` thì fix tại facade, không sửa explorer.
4. Mọi thay đổi hành vi module khác = regression → fail R4.
