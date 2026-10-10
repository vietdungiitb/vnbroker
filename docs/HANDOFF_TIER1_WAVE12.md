# HANDOVER — Tier-1 Wave 1 + Wave 2 (bàn giao cho session sau)

**Trạng thái tại bàn giao:** đã merge + push, tag `v3.6.0`.
**Cây:** `main` ← `dev` ← `feat/tier1-wave12` (`a907b83`)
**Cổng vào duy nhất:** `pwsh -File scripts\check_all.ps1` — exit 0 ở trạng thái này.
**Lessons áp dụng:** L-E01 · L-E02 · L-E03 · L-E04 · L-E06 · L-E07 · L-P01 · L-P03 · L-P05 · L-P06 · L-R04

---

## 1. NHẬT KÝ CÔNG VIỆC ĐÃ HOÀN THÀNH

### 1.1 Đợt này — 4 commit trên `feat/tier1-wave12`

| Commit | Nội dung |
|:--|:--|
| `08ed9e3` | Wave 2 (chuẩn hoá) + Wave 1 (provider) + cổng `check_provider_consistency.py` |
| `06d7e4f` | Sửa 5 lỗi audit vòng 1 (1 blocker + 1 major + 3 minor) |
| `80cdd2e` | Sửa 7 lỗi audit vòng 2 (7 major) + cô lập biến cho test |
| `a907b83` | Sửa lỗi thứ 5 trong chuỗi TCBS (facade ghi đè token) |

### 1.2 Vấn đề đã sửa — kèm bằng chứng

| # | Vấn đề | Trước | Sau | Bằng chứng tái lập |
|:--|:--|:--|:--|:--|
| 1 | **`match_type` lệch casing giữa provider** | KBS `buy/sell/atc` · VCI `Buy/Sell/ATC`; `df[df.match_type=='Buy']` → KBS **0** dòng, VCI **67** | cả hai `['ATC','Buy','Sell']`; KBS **74** dòng | nguyên nhân: `explorer/kbs/quote.py` gọi `.str.lower()` ngay sau `process_match_types`. Đây là **dòng duy nhất** trong toàn repo làm vậy (`grep str.lower()`). |
| 2 | **Đơn vị lưu trữ `time` lệch** | KBS `[us]` · VCI `[s]`; `DataFrame.concat` ra **`object`** | cả hai `[ns, Asia/Ho_Chi_Minh]` | pandas ≥2 giữ nguyên đơn vị nguồn; `concat` không tìm thấy dtype chung |
| 3 | **Hai bản chuẩn hoá trùng nhau** | `normalizer.py` + `data.py`, không ai đối chiếu | `data.py` chỉ còn là lớp gọi | `tests/contract/test_normalizer_contract.py::test_normalizer_is_the_single_implementation` |
| 4 | **`api/quote.py` không đi qua tầng chuẩn hoá** | trả frame thô | qua `Normalizer` | ⚠ phải sửa ở `_post_process_result`, **không** sửa trong thân hàm — xem mục 4.1 |
| 5 | **`api/bulk.py` `pd.concat` frame thô** | giữ nguyên đơn vị provider | chuẩn hoá từng frame trước concat | đo live: `BulkAPI.history(['VCB','TCB'])` → `[ns, tz]`, 40 dòng |
| 6 | **`market_cap` phóng đại 1000 lần** | VCB **473 766 777.83** tỷ | **473 766.78** tỷ | nguyên nhân: `api/snapshot.py` suy đơn vị từ **tham số** `price_unit` thay vì đọc `df.attrs['price_unit']` mà provider dán |
| 7 | **TCBS đọc sai biến token** | `TCBS_AUTH_TOKEN` (48 ký tự, server 401) | ưu tiên `TCBS_JWT_TOKEN` (1290 ký tự, HTTP 200) | đo: token 48 ký tự → `401 validate.token.error` trên **4/4** endpoint |
| 8 | **Facade ghi đè token của provider** | `common/client.py` đọc thẳng `TCBS_AUTH_TOKEN` | gọi `resolve_auth_token()` — một nguồn | đo: `Vnbroker(source='TCBS').stock('TCB').quote.history()` → `ConnectionError` trong khi gọi provider trực tiếp ra 20 dòng |
| 9 | **`ProviderPool` đòi biến không tồn tại** | `TCBS_API_SECRET` — không có ở đâu | đọc `TCBS_JWT_TOKEN` | đo: `.env` có JWT hợp lệ mà `has_auth tcbs = False` |
| 10 | **`screener` chết trong `AUTO`** | `AUTO = []` dù registry có `kbs`/`vci` | `['kbs','vci']` | nguồn: `OPEN_SOURCE_CANDIDATES` là danh sách viết tay, không ai đối chiếu |
| 11 | **Ba danh sách provider lệch nhau** | không có cổng | `scripts/check_provider_consistency.py` (C0–C5) + self-test 5 ca âm | C4 bắt được `rss_cafef`/`rss_vneconomy` thiếu trong `NO_AUTH_PROVIDERS` — **lỗi dữ liệu thật** |
| 12 | **14 test phụ thuộc `.env` của máy** | `pytest tests/unit tests/contract` xanh nhưng `pytest tests/` **14 failed** | fixture `autouse` cô lập credential | xem mục 4.2 |
| 13 | **Thông báo lỗi chỉ sai biến** | "set TCBS_AUTH_TOKEN=\<JWT\>" | "set TCBS_JWT_TOKEN=\<JWT\>" | đo: làm theo hướng dẫn cũ vẫn 401 |

### 1.3 Kiểm chứng bằng dữ liệu thật (mã TCB, 2026-10-10)

Trước → sau, cùng một lệnh:

| Lệnh | Trước (`9d5db1d`) | Sau (`a907b83`) |
|:--|:--|:--|
| `df[df.match_type=='Buy']` (KBS) | **0** | **74** |
| `pd.concat([KBS,VCI])['time'].dtype` | **`object`** | `datetime64[ns, Asia/Ho_Chi_Minh]` |
| `heatmap_df(['VCB'])['market_cap']` | **473 766 777.83** tỷ | **473 766.78** tỷ |
| `Vnbroker(source='TCBS').stock('TCB').quote.history()` | `ConnectionError` | **20 dòng** |
| `get_auto_candidates('screener')` | `[]` | `['kbs','vci']` |

### 1.4 Cổng mới

`scripts/check_provider_consistency.py` — 5 quy tắc:

| Quy tắc | Bắt cái gì |
|:--|:--|
| **C0** | `env_any`/`env_all` phải là **tuple**, không phải chuỗi. `_first_env` duyệt theo phần tử nên chuỗi bị duyệt thành từng ký tự → provider biến mất khỏi pool im lặng. |
| **C1** | Provider có credential thật phải được pool nhận diện cho **từng** module nó khai hỗ trợ. |
| **C2** | Module có provider dùng được thì `get_auto_candidates` không được trả `[]`. |
| **C3** | Provider trong AUTO phải tồn tại trong registry (tên chết ⇒ failover vào hư không). |
| **C4** | Provider đã đăng ký, không phải no-auth, thì **phải có** mục cấu hình credential. |
| **C5** | Provider pool phục vụ được cho module thì **phải** xuất hiện trong AUTO của module đó. |

`--self-test`: 5 trường hợp âm. Đã **phòng thủ** bằng cách tiêm lại 3 lỗi mà
bản cổng cũ im lặng — cả 3 đều bị bắt (exit 1), cây sạch exit 0.

---

## 2. ĐÍNH CHÍNH 3 ĐIỀU PHIÊN TRƯỚC NÓI SAI

Ghi lại vì tài liệu cũ vẫn còn và đọc dễ tin (L-E01).

| Điều được bàn giao | Thực tế |
|:--|:--|
| "KBS `intraday()` trả tz-**naive**" | **SAI.** Đo: `datetime64[us, Asia/Ho_Chi_Minh]` — tz-**aware**. `common/data.py` đã chuẩn hoá từ lâu. Lỗi thật là **khác đơn vị**, không phải thiếu tz. |
| "TCBS nối sai biến" | **ĐÚNG**, nhưng chỉ là 1 trong **5** lỗi trong chuỗi. Sửa 1 chỗ không đủ — phải sửa tới khi `Vnbroker(source='TCBS')` chạy thật. |
| "DNSE lỗi mạng chập chờn" | **ĐÚNG** về triệu chứng, nhưng đã tìm ra nguyên nhân tầng mạng: TLS handshake tới `openapi.dnse.com.vn` **timeout**, trong khi `api.dnse.com.vn` và `ws-openapi.dnse.com.vn` TLS OK. Không phải credential, không phải flake. |

⚠ **Số đếm bằng PowerShell sai.** `Get-Content | Measure-Object -Line` cho **1583**
dòng với `common/data.py`; `len(text.splitlines())` cho **1876**. Đếm bằng
PowerShell làm tôi tưởng chỉ 5 file vượt 800L thay vì **11**. Hãy dùng Python cho
số dòng.

---

## 3. TÌNH TRẠNG ĐO ĐƯỢC (kế hoạch cha vẫn còn giá trị)

| Hạng mục | Số | Cách đo lại |
|:--|:--|:--|
| Gate | **8 PASS · 1 KNOWN-RED · 0 CHƯA CHẠY · exit 0** | `pwsh -File scripts\check_all.ps1` |
| Test | **1978 passed · 26 skipped** | `pytest tests/ -q --timeout=300` |
| Contract | **91 passed** (baseline 72) | `pytest tests/contract -q` |
| mypy | baseline 1266 → **1138**, không lỗi mới | `python scripts/check_mypy_baseline.py` |
| ruff | 0 trên `vnbroker scripts tests/unit tests/contract` | `python -m ruff check …` |
| File >800L | **11** | `python -c "…rglob('*.py')…len(splitlines())"` |
| CI | **CHƯA CHẠY** (billing) | in ở cuối mỗi lần chạy `check_all.ps1` |

⚠ **Không** dùng `mypy vnbroker --strict` như gate — `strict = true` trong
`[[tool.mypy.overrides]]` bị nâng thành global, nên cả hai lệnh cho 1207 lỗi
y hệt. Gate thật là `check_mypy_baseline.py`.

---

## 4. CÁI GÌ ĐÃ TỐN NHIỀU THỜI GIAN NHẤT — ĐỪNG LÀM LẠI

### 4.1 `@dynamic_method` cắt bỏ thân hàm

`vnbroker/base.py:21`. `history`/`intraday` của `api.quote.Quote` có decorator
này; nó rẽ sang `_call_dynamic_method` **trước khi thân hàm chạy**. Bản sửa đầu
tiên đặt `self._normalize(...)` trong thân hàm — đọc rất hợp lý, không test nào
chạm tới, và **không bao giờ chạy**. Đo: `_delegate_to_provider` gọi **0** lần.

Điểm móc đúng là `BaseAdapter._post_process_result`, gọi từ
`_invoke_provider_method`. Test khoá:
`tests/contract/test_normalizer_contract.py::test_api_quote_adapter_normalizes_even_though_body_is_dead_code`.

### 4.2 `.env` của máy làm test phụ thuộc môi trường

`tests/conftest.py` nạp `.env` thật vào `os.environ`, nên test viết
`assert get_auto_candidates('quote') == ['vci','kbs']` **đỏ trên máy có
credential** và **xanh trên máy không có**. Đo được: `pytest tests/unit
tests/contract` → 1873 passed, `pytest tests/` → **14 failed**, cùng một commit.

Đã sửa bằng fixture `autouse` ở `tests/unit/conftest.py` + `tests/contract/conftest.py`
(**không** đặt ở `tests/conftest.py` — `tests/integration` cần credential thật).
Danh sách biến derive từ `ProviderPool.AUTH_PROVIDERS`, không liệt kê tay.

### 4.3 Cổng báo "OK" trong khi kết luận là FAIL

Bản cổng đầu tiên trả exit 2 khi máy không có `.env` ⇒ `check_all.ps1` in
`FAIL provider-consistency exit=2 OK: khong co vi pham nao.` Một dòng vừa đỏ
vừa xanh. Nay thiếu `.env` chỉ là **cảnh báo** (exit 0), exit 2 dành cho "gate
không chạy được", và `check_all.ps1` có trạng thái `CHUA CHAY` riêng.

### 4.4 Lỗi do chính tác giả viết, do gate bắt

| Lỗi | Bắt bởi |
|:--|:--|
| `_first_env` duyệt **chuỗi** thành từng ký tự → provider biến mất khỏi pool | `check_provider_consistency.py` |
| Đảo ngược nhánh `multiplier` trong `_compute_market_cap` (nhân 1000 khi đã là VND) | AC-3 |
| Cổng báo nhầm trên cấu hình **đúng** (hardcode `quote`) | audit vòng 2 |
| `env_all` tính rồi bỏ qua | ruff `F841` — sau khi thêm `scripts` vào phạm vi lint |

---

## 5. CÒN TỒN ĐỌNG — theo thứ tự ưu tiên

### P0 — ảnh hưởng người dùng, sửa được ngay

| # | Việc | Bằng chứng hiện trạng | Gợi ý |
|:--|:--|:--|:--|
| **B1** | **TCBS không có side cho `intraday`** | Đo raw `/nyx/v1/intraday/TCB/his/paging`: `"a": ""` cho **mọi** bản ghi ⇒ `match_type` toàn `unknown`, trong khi KBS/VCI có `Buy`/`Sell`. | Đây là **server**, không phải mapping. `AUTO` chọn TCBS cho `intraday` sẽ cho kết quả không phân biệt được mua/bán. **Cần quyết định của Owner**: (a) loại `intraday` khỏi `tcbs` khỏi AUTO, hay (b) chấp nhận và ghi rõ. Không được bịa dữ liệu. |
| **B2** | **DNSE không tới được từ máy này** | `ConnectionResetError(10054)` 3/3; TLS handshake tới `openapi.dnse.com.vn` **timeout**; `api.dnse.com.vn` + `ws-openapi.dnse.com.vn` TLS OK. | Kiểm tra tường lửa/VPN, hoặc đổi base URL cho đường đi được. **Đừng** kết luận "DNSE hỏng" — chỉ ghi `CHƯA CHẠY` kèm lý do tầng mạng. |

### P1 — quyết định kiến trúc, cần Owner

| # | Việc | Vì sao chưa làm |
|:--|:--|:--|
| **A1** | `import vnbroker` **không** nạp `.env` | Không có `python-dotenv` trong deps; nạp ngầm là thay đổi có rủi ro bảo mật. Hiện tại người dùng phải tự `export`. Cổng tự nạp nên **gate vẫn kiểm được**. Cần Owner chọn: nạp `.env`, hay tài liệu hoá rõ rằng phải export. |
| **A2** | Provider có credential đang **nối cuối** danh sách AUTO | Không có benchmark. Đây là lựa chọn có chủ ý: không ai lên đầu khi không có số đo — đúng như `SSI_AUTO_CANDIDATES` sẵn có. Muốn đưa TCBS/DNSE lên đầu thì cần đo p99 latency + tỉ lệ lỗi trên cả ba. |
| **A3** | `screener` của VCI và KBS trả **0 dòng** | Đo: `stock(limit=50)`, `stock(limit=1000)`, `stock(params={'symbols': [...]})` đều 0. Chưa biết là endpoint đổi, hay tham số sai, hay cần filter khác. |

### P2 — nợ kỹ thuật có sẵn, không do đợt này

| # | Việc | Số đo |
|:--|:--|:--|
| **T1** | 11 file vượt 800L | `common/data.py` 1876 · `connector/dnse/trade.py` 1352 · `core/utils/field/kbs_mappings.py` 1304 · `core/utils/parser.py` 1106 · `core/utils/transform.py` 1056 · + 6 file |
| **T2** | `ruff check tests` KNOWN-RED | 13 lỗi F401/F841 có sẵn ở `9d5db1d` |
| **T3** | `mypy vnbroker` 1207 lỗi có sẵn | baseline 1266 → 1138; giảm dần qua từng lát |
| **T4** | `logger.SENSITIVE_PATTERN` (`core/utils/logger.py:24-27`) lọt token trần | Regex cần dạng `key<sep>value`; `str({"Authorization": f"Bearer {JWT}"})` lọt vì lớp ký tự dừng ở dấu cách. **Đây là logger của lane tiền thật** — nên ưu tiên hơn vẻ ngoài. |
| **T5** | Bộ đọc `.env` của cổng không bóc dấu nháy, không xử lý `export` | Vô hại hôm nay (`.env` thật: 8 khoá, 0 khoá có nháy) |
| **T6** | Wave 3 — rate-limit thật (`X-RateLimit-*`, `Retry-After`, token-bucket) | Giữ nguyên lý do hoãn của kế hoạch cha §6: rate-limit chỉ hữu ích khi router đã thấy provider nào còn quota. **Điều kiện đó nay đã có** — AUTO có 4 provider thay vì 2. Wave 3 **nên làm tiếp theo**. |

---

## 6. CHECKLIST CHO SESSION SAU

```powershell
# 0. Bắt buộc đặt trước khi in bất cứ thứ gì có dấu tiếng Việt
$env:PYTHONIOENCODING="utf-8"     # console cp1252 → UnicodeEncodeError

# 1. Cổng đầy đủ (KHÔNG dùng -Quick trước khi merge)
pwsh -File scripts\check_all.ps1
#    kỳ vọng: 8 PASS · 1 KNOWN-RED (ruff-tests-all) · 0 FAIL · exit 0

# 2. Cổng mới + tự kiểm chính nó
.venv\Scripts\python.exe scripts\check_provider_consistency.py
.venv\Scripts\python.exe scripts\check_provider_consistency.py --self-test
```

Trước khi viết plan, **bắt buộc** nạp skill `project-lessons` và đọc
`docs/LESSONS/{evidence,process,broker-risk}.md` theo tag; mọi plan phải có
dòng `Lessons áp dụng: [...]`.

Trước khi sửa `vnbroker/broker/**` (tiền thật): **bắt buộc** đọc
`docs/LESSONS/broker-risk.md`.

---

## 7. VÍ DỤ ĐO LẠI NHANH

```powershell
# Provider nào thật sự vào AUTO (không in giá trị credential)
.venv\Scripts\python.exe -c @"
import os, pathlib, sys; sys.path.insert(0, os.getcwd())
for l in pathlib.Path('.env').read_text(encoding='utf-8').splitlines():
    l=l.strip()
    if l and not l.startswith('#') and '=' in l:
        k,v=l.split('=',1); os.environ.setdefault(k.strip(), v.strip())
import vnbroker; vnbroker._ensure_explorer_modules_loaded()
from vnbroker.core.source_router import get_auto_candidates
for m in ('quote','trading','listing','screener'):
    print(m, get_auto_candidates(m))
"@
```

**Lệnh AC đầy đủ** (11 kiểm tra, 3/11 trước → 11/11 sau) và **script khiêm chứng
gate** nằm ở `%TEMP%\opencode\` của máy Owner: `prove_fail_before.py`,
`probe_gate_defense2.py`, `final_live_check.py`. Chúng **không** commit vào repo
vì chứa logic đo phụ thuộc `.env` thật — nếu muốn giữ lâu dài thì chuyển thành
script trong `scripts/` với `.env` tổng hợp, và khi đó cần Owner duyệt vì nó đọc
credential.