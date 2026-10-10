# PLAN — Tier-1 Wave 1 + Wave 2: dữ liệu đúng và provider thật

**Ngày:** 2026-10-10 · **Base:** `dev @ 9d5db1d` · **Repo:** `vnbroker`
**Kế hoạch cha:** `docs/PLAN_TIER1_PROVIDER_AGNOSTIC.md`
**Audit đầu vào:** `docs/AUDIT_TIER1_RECHECK_20261010.md`, `docs/REPORT_TIER1_EXPLORER_SURVEY.md`
**Lessons áp dụng:** L-E01 (số phải kèm lệnh) · L-E02 (spec/pin trong repo) · L-E03 (gate tự kiểm input)
· L-E04 (một lần đỏ không phải kết luận) · L-E05 (tiêu chí theo giá trị cụ thể) · L-E06 (fail-trước chạm
đúng tầng lỗi) · L-E07 (không so số giữa 2 lần chạy) · L-P01 (ghi rõ nơi đo) · L-P03 (chốt mâu thuẫn
thiết kế) · L-P04 (mọi file cần sửa đều có chủ) · L-P05 (đo lại, đừng tin lời agent) · L-P06 (AC phải
thi hành được) · L-R01 (HTTP 200 ≠ thành công) · L-R03 (field null) · L-R04 (không probe được thì đừng
kết luận) · L-R07 (gợi ý sửa theo hướng mất tiền)

**Chế độ thực thi:** Mode B cho phần ghi code (một người viết) + **3 audit độc lập read-only**
(Stage 2 / Stage 5 / Stage 6). Giữ đúng lý do `PLAN_TIER1_PROVIDER_AGNOSTIC.md` §0: các lát cắt chạm
đúng những file đường gây tiền; "treat a second agent as a second opinion | same file, same tool,
same misreading".

---

## 0. ĐÍNH CHÍNH — claim của phiên trước, đo lại

Bốn claim được bàn giao. **Hai đúng, một sai, một đúng-nhưng-sai-nguyên-nhân.** Số đo ở
`dev @ 9d5db1d`, ngày 2026-10-10, máy của Owner, `.env` thật.

| # | Claim của phiên trước | Kết luận | Bằng chứng tái lập |
|:--|:--|:--|:--|
| C1 | TCBS nối sai biến môi trường, JWT chạy được | **ĐÚNG** | `explorer/tcbs/auth.py:11-14` chỉ đọc `vnbroker_TCBS_AUTH_TOKEN`/`TCBS_AUTH_TOKEN`. Đo: `resolve_auth_token()` → len **48**; `TCBS_JWT_TOKEN` len **1290**. `TCBSQuote(symbol="TCB").history(...)` → `ConnectionError`. Truyền `auth_token=TCBS_JWT_TOKEN` → **20 dòng**. Token 48 ký tự → HTTP **401** `{"code":"validate.token.error"}` trên 4/4 endpoint |
| C2 | DNSE chưa chạy, `ConnectionResetError(10054)` | **ĐÚNG — và đã tìm ra nguyên nhân tầng mạng** | `ConnectionResetError` ×3 lần chạy liên tiếp. Tầng socket: `openapi.dnse.com.vn:443` **TLS handshake timeout**; `api.dnse.com.vn` + `ws-openapi.dnse.com.vn` TLS **OK**. ⇒ explorer trỏ vào host máy này không bắt tay được. Không phải credential, không phải flake |
| C3 | "KBS `intraday()` trả tz-**naive**" | **SAI — đính chính** | `Vnbroker(source="KBS").stock("TCB").quote.intraday()["time"].dtype` = `datetime64[us, Asia/Ho_Chi_Minh]` — **tz-aware**. `common/data.py:769-772` đã chuẩn hoá. Hậu quả: kế hoạch cha ghi "chứng minh bằng script: `api/quote.py` không gọi Normalizer" là **đúng**, nhưng lý do "KBS tz-naive" thì sai |
| C4 | `pd.concat` → `dtype object` | **ĐÚNG — nhưng nguyên nhân khác** | Không phải naive-vs-aware (cả hai đều aware). Là **khác đơn vị**: KBS `[us]` vs VCI `[s]`. Đo trên frame thật: `pd.concat([kbs_df, vci_df])["time"].dtype` = **`object`**; `concat` riêng 2 Series thì ra `[us]` — chỉ `DataFrame.concat` mới hỏng. Sau `as_unit("ns")` cả hai → `datetime64[ns, Asia/Ho_Chi_Minh]` |

**Số trong tài liệu cũ đã kiểm lại (L-E01):** `PLAN_TIER1_PROVIDER_AGNOSTIC.md` §7 ghi *"11 file vượt
800L"*. Đếm lại bằng `python -c "...rglob('*.py')...len(splitlines())"` ở `9d5db1d` → **11 file > 800L**
(`common/data.py` 1876 · `connector/dnse/trade.py` 1352 · `core/utils/field/kbs_mappings.py` 1304 ·
`core/utils/parser.py` 1106 · `core/utils/transform.py` 1056 · `explorer/kbs/financial.py` 828 ·
`broker/tcbs/client.py` 827 · `broker/ssi/stream.py` 825 · `connector/dnse/websocket.py` 811 ·
`explorer/kbs/company.py` 808 · `explorer/tcbs/quote.py` 793… **giữ nguyên con số, đã xác nhận**).

⚠ **PowerShell `Get-Content | Measure-Object -Line` ra 1583 cho `common/data.py` — SAI.**
Python `len(text.splitlines())` ra 1876. Đếm bằng PowerShell đã làm tôi tưởng chỉ có 5 file vượt ngân
sách. Đây là L-E01 ở dạng mới: **công cụ đếm khác nhau cho hai con số khác nhau, phải chọn một
nguồn sự thật và ghi tên nó.**

---

## 1. Q2 ĐÃ TRẢ LỜI — provider trả **VND**, `snapshot.py` nhân ×1000 là SAI

Câu hỏi mở từ phiên trước: *"provider trả giá VND hay nghìn VND?"*. Đo live, không suy luận:

```
KBS price_board(['VCB'], get_all=True, price_unit=None)
  attrs['price_unit'] = 'VND'   close_price = 56700   listed_shares = 8355675094
KBS price_board(['VCB'], get_all=True, price_unit='VND')
  attrs['price_unit'] = 'VND'   close_price = 56700   ← Y HỆT
```

**Hai lệnh cho ra cùng một con số ⇒ `price_unit=None` KHÔNG có nghĩa là "nghìn VND".**

| `_compute_market_cap(price_unit=…)` | Kết quả (tỷ VND) | Đúng? |
|:--|--:|:--|
| `None` (mặc định của `heatmap_data`) | **473 766 777.83** | ❌ phóng đại **×1000** |
| `"VND"` | 473 766.78 | ✅ |
| — đối chiếu thực tế — | `56700 × 8355675094 / 1e9` = **473 766.78** | ✅ |

VCB vốn hoá ~474 nghìn tỷ VND — con số đúng. ⇒ `multiplier = 1_000` tại `api/snapshot.py:358` là
**sai**, và `df_out.attrs["price_unit"] = price_unit or "nghìn VND"` (`:314`) **cũng sai** (dán nhãn
"nghìn VND" lên dữ liệu VND).

**Cơ chế (đọc code, khớp đo):** `explorer/kbs/trading.py:224-230` gọi
`normalize_price_columns(..., source_unit='VND', target_unit=price_unit)`;
`core/utils/transform.py:78-80` khi `target_unit is None` thì lấy `_resolve_target_price_unit()` =
env `vnbroker_PRICE_UNIT`, **mặc định `"VND"`**. Nên provider **tự dán** `df.attrs['price_unit']`
đúng đơn vị thực.

⇒ **Fix không cần đoán**: đọc `df.attrs['price_unit']` (nguồn sự thật do chính provider dán), suy
ra `multiplier` từ nó. `price_unit` truyền vào chỉ là *ý muốn*, không phải *sự thật*.

**Q3 (cho phép probe bằng API key trong `.env` để chốt Q2) — ĐÃ DÙNG, và không cần.** Q2 chốt
được bằng GET-only read-only trên `price_board`, không gọi write endpoint nào. Không có credential
nào bị in ra transcript (chỉ tên biến + độ dài).

---

## 2. BASELINE GATE — đo ở `9d5db1d`, trước khi đòi bất cứ điều gì

`pwsh -File scripts/check_all.ps1 -Quick` @ `9d5db1d`, exit **0**:

| Gate | Exit | Ghi chú |
|:--|:--|:--|
| ruff-src | 0 | `All checks passed!` |
| ruff-tests-all | **1** | 13 lỗi có sẵn — **KNOWN-RED**, không tính FAIL |
| version-sync | 0 | 3.5.0 khớp 5 nơi |
| lessons | 0 | 24/40 lesson, 5 file |
| tcbs-coverage | 0 | spec sha256 `7f97d27b…` khớp |
| tcbs-bodies | 0 | lệch đã biết: 0 |
| mypy-baseline | 0 | baseline 1266 → now 1138 (fixed 128) |
| pytest-contract | 0 | 72 passed |
| pytest-full | SKIP | `-Quick`; **bắt buộc chạy lại không `-Quick` trước khi merge** |

Hazard 6: **không AC nào ở đây được phép đòi `ruff-tests-all` = 0** — nó đang đỏ sẵn.
Hazard 9: `CI GITHUB ACTIONS: CHUA CHAY` — script in rõ, mọi gate phải chạy local.

---

## 3. AC — đo thứ người dùng quan tâm

> *"Nếu AC pass nhưng tính năng vẫn vô dụng, AC có bắt được không?"* (hazard 8)

| AC | Given/When/Then | Vì sao không phải proxy |
|:--|:--|:--|
| **AC-1** | `df[df.match_type == "Buy"]` trên `intraday()` của **KBS và VCI** cho **cùng một tập ngữ nghĩa**, và **>0 dòng** ở cả hai | Đo được trực tiếp trên frame thật: hiện tại KBS **0**, VCI **67**. Không chấp nhận "tồn tại cột match_type" |
| **AC-2** | `pd.concat([kbs_intraday, vci_intraday])["time"].dtype` là **datetime tz-aware**, không phải `object` | Đo được: hiện tại `object`. Đây chính là lỗi người dùng gặp hôm nay |
| **AC-3** | `MarketSnapshot().heatmap_df(["VCB"])` với `price_unit=None` ⇒ `market_cap` khớp `close_price × listed_shares / 1e9` trong **sai số < 0.01%**; và `attrs['price_unit']` nói đúng đơn vị | Chống đúng proxy "trả về con số". Đo được: hiện lệch ×1000 |
| **AC-4** | `resolve_auth_token()` trả **JWT** khi `TCBS_JWT_TOKEN` có; `TCBSQuote(symbol="TCB").history()` **không ném** | AC là "gọi thật thành công", không phải "đọc đúng biến" |
| **AC-5** | `get_auto_candidates(m)` **không rỗng** cho mọi module mà `ProviderRegistry.list_available(m)` có provider **có credential** | Đo được: hiện `screener`/`indices`/`live`/`snapshot` = `[]` |
| **AC-6** | Provider có credential trong `.env` mà registry có implementation ⇒ xuất hiện trong `ProviderPool.get_available_providers` | Đo được: hiện TCBS vắng dù `.env` có token chạy được |
| **AC-7** | `python scripts/check_provider_consistency.py` **exit ≠ 0** khi cấu hình provider mâu thuẫn (self-test âm) | Gate chưa tồn tại — phải viết self-test âm theo hazard "gate chỉ chạy trên input sạch" |

**Ràng buộc chống tự lừa (hazard 10):** mỗi test mới phải **ĐỎ trên bản trước khi sửa**.
Cách làm: `git show 9d5db1d:<file> > <file-tạm>` → chạy → khôi phục. **Không** dùng
`git checkout --` (hazard 11).

---

## 4. WAVE 2 — dữ liệu đúng bất kể provider (P0)

**File:** `core/utils/normalizer.py` · `common/data.py` · `explorer/kbs/quote.py` ·
`api/quote.py` · `api/bulk.py` · `api/snapshot.py` · `core/bulk_router.py`

| Việc | Nguyên nhân đã ĐO |
|:--|:--|
| **W2.5** Xoá 1 trong 2 bản chuẩn hoá trùng; `common/data.py` gọi `Normalizer` | `normalizer.py:55-78` và `data.py:838-881` cùng logic. Nguồn sự thật: `core/utils/normalizer.py` (docstring đầy đủ hơn, không phụ thuộc `common`) |
| **W2.2** Ép `time` về **một đơn vị** `datetime64[ns, Asia/Ho_Chi_Minh]` | Đo: KBS `[us]` vs VCI `[s]` ⇒ `DataFrame.concat` → `object`. pandas 3 giữ nguyên đơn vị nguồn |
| **W2.1** `match_type` về một tập giá trị | **Một dòng**: `explorer/kbs/quote.py:672` `.str.lower()` phá hợp đồng mà `process_match_types` vừa lập 3 dòng trên. Đo: KBS `buy/sell/atc` vs VCI `Buy/Sell/ATC` |
| **W2.6** `api/quote.py` đi qua cùng tầng | `api/quote.py` có **0** tham chiếu `Normalizer`. Đo: chỉ `tests/` + `tests/examples/` import `vnbroker.api.quote.Quote` — bề mặt công khai nhưng **không** nằm trên đường `Vnbroker.stock()` ⇒ **major, không phải blocker** |
| **W2.3** `BulkRouter`/`BulkAPI` chuẩn hoá trước `concat` | `api/bulk.py:114-115` chỉ `pd.concat` + `sort_values` |
| **W2.4** `market_cap` theo `df.attrs['price_unit']` | Đo ở §1: lệch ×1000 |

**Chốt thiết kế trước khi giao (L-P03):**
- `Normalizer` **không** import `transform` ở module scope (chuỗi import) — import trong hàm.
- `Normalizer` **không** chạy lại heuristic ATO/ATC của `process_match_types` (cần `time.dt`,
  thêm cột `date`, `groupby.apply` mutate). Tầng chuẩn hoá chỉ đảm bảo **từ vựng**; ATO/ATC là
  phán đoán tầng provider và đã chạy sẵn ở KBS/VCI.
- `Normalizer` giữ **không mutate** frame của provider (`test_layer_normalization.py:154` khoá).

---

## 5. WAVE 1 — provider thật (P1)

**File:** `explorer/tcbs/auth.py` · `core/provider_pool.py` · `core/source_router.py` ·
`CLAUDE.md` · `scripts/check_provider_consistency.py` (mới)

| Việc | Nguyên nhân đã ĐO |
|:--|:--|
| **W1.0** `resolve_auth_token()` ưu tiên `TCBS_JWT_TOKEN` | Đo §0 C1. Thứ đang làm TCBS hỏng |
| **W1.1** `ProviderPool` đọc biến `.env` thật cho TCBS | `TCBS_API_KEY`/`TCBS_API_SECRET` **không tồn tại** trong `.env` (đo: `has_auth tcbs = False`) |
| **W1.2** `get_auto_candidates()` không trả `[]` khi registry có provider | Đo §0 H: `screener`/`indices`/`live`/`snapshot` = `[]` |
| **W1.4** Cổng `check_provider_consistency.py` + self-test âm | Chặn tái phát 3 danh sách provider mâu thuẫn |

**Không** thêm ưu tiên ưu tiên riêng cho TCBS/DNSE — chưa có số đo hiệu năng.

⚠ **DNSE không được coi là "đã ổn định".** Đo: TLS handshake tới `openapi.dnse.com.vn` **timeout**.
Cho tới khi đo được data thật, DNSE **không** được đưa vào `PRIMARY_SOURCE_POOLS`, và mọi kết luận
về DNSE ghi `CHƯA CHẠY` kèm lý do tầng mạng (L-R04).

---

## 6. NGOÀI PHẠM VI

- ❌ `vnbroker/broker/**` — lane tiền thật, không đụng
- ❌ Không gọi write endpoint; mọi probe là GET-only
- ❌ Không sửa 11 file vượt 800L ngoài phần chạm tối thiểu
- ❌ Wave 3 (rate-limit thật) — để đợt sau, có lý do ở `PLAN_TIER1_PROVIDER_AGNOSTIC.md` §6
- ❌ Không kết luận "DNSE ổn" — chưa đo được

---

## 7. ĐỊNH NGHĨA XONG

Wave 1+2 xong khi: AC-1..AC-7 xanh **và** `check_all.ps1` (không `-Quick`) exit 0 **và** audit Stage 5
báo **0 blocker + 0 major** **và** mỗi số trong báo cáo có lệnh tái lập.
