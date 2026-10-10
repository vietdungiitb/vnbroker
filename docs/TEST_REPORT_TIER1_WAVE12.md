# TEST REPORT — Tier-1 Wave 1 + Wave 2

**Cây:** `feat/tier1-wave12` @ `a907b83` · **Ngày:** 2026-10-10 · **Máy:** Windows 11, Python 3.13.14, pandas 3.0.2, numpy 2.4.4
**Lệnh:** `pwsh -File scripts/check_all.ps1` (không `-Quick`)

> Mọi dòng dưới đây là **kết quả quan sát được**, không phải kỳ vọng.
> `CHƯA CHẠY` là kết quả hợp lệ; suy đoán "chắc là ổn" từ một gate chưa chạy
> chính là cách một bản deploy hỏng đi lọt.

---

## 1. Bảng gate — một dòng cho mỗi gate

| Gate | Lệnh thật | Exit | Kết luận |
|:--|:--|:--:|:--|
| ruff-src | `python -m ruff check vnbroker scripts tests/unit tests/contract` | 0 | **Pass** |
| ruff-tests-all | `python -m ruff check tests` | 1 | **KNOWN-RED** — 13 lỗi F401/F841 có sẵn ở `9d5db1d`, không do đợt này |
| version-sync | `python scripts/check_version_sync.py` | 0 | **Pass** — 3.5.0 khớp 5 nơi |
| lessons | `python scripts/check_lessons.py` | 0 | **Pass** — 24/40 lesson, 5 file |
| tcbs-coverage | `python scripts/verify_tcbs_coverage.py` | 0 | **Pass** — spec sha256 `7f97d27b…` khớp |
| tcbs-bodies | `python scripts/check_tcbs_bodies.py --baseline docs/tcbs_body_baseline.json` | 0 | **Pass** — lệch đã biết: 0 |
| provider-consistency | `python scripts/check_provider_consistency.py` | 0 | **Pass** — cổng MỚI, xem §3 |
| mypy-baseline | `python scripts/check_mypy_baseline.py` | 0 | **Pass** — baseline 1266 → 1138, **không lỗi mới** |
| pytest-contract | `pytest tests/contract -q` | 0 | **Pass** — **91 passed** |
| pytest-full | `pytest tests/ -q --timeout=300` | 0 | **Pass** — **1978 passed, 26 skipped** |
| self-test: lessons | `python scripts/check_lessons.py --self-test` | 0 | **Pass** |
| self-test: tcbs-bodies | `python scripts/check_tcbs_bodies.py --self-test` | 0 | **Pass** |
| self-test: provider-consistency | `python scripts/check_provider_consistency.py --self-test` | 0 | **Pass** — 5 trường hợp âm, tất cả RED |

**Tổng `check_all.ps1`: exit 0.** 8 gate PASS · 1 KNOWN-RED · 0 CHƯA CHẠY.

⚠ **CI GITHUB ACTIONS: CHƯA CHẠY** (job bị từ chối khởi động do billing). Script in
rõ điều này ở cuối mỗi lần chạy. Đừng tin badge CI.

---

## 2. Bằng chứng đỏ-trước / xanh-sau

Không dùng `git checkout --` (hazard 11): `git show 9d5db1d:<file>` ghi đè tạm,
chạy, rồi khôi phục từ bản sao trong `%TEMP%`.

| AC | ĐỎ trước | XANH sau |
|:--|:--|:--|
| AC-1 tập giá trị `match_type` giống nhau | KBS `['buy','sell']` vs VCI `['Buy','Sell']` | cả hai `['Buy','Sell']` |
| AC-1 `df[df.match_type=='Buy']` ra dòng ở cả hai | **KBS 0** · VCI 2 | KBS 2 · VCI 2 |
| AC-2 cùng đơn vị lưu trữ | KBS `[us]` · VCI `[s]` | cả hai `[ns, Asia/Ho_Chi_Minh]` |
| AC-3 `market_cap` đúng khi `price_unit=None` | **lệch 99 899.9995%** (`473766777.83` vs `473766.78`) | lệch **0.0000%** |
| AC-4 `resolve_auth_token` trả JWT | len 48, không phải JWT | len 1290, 3 phần |
| AC-6 pool nhận diện TCBS | `has_auth tcbs = False` | `True`, vào `AUTO` |
| AC-5 `screener` không chết | `AUTO=[]` | `AUTO=['kbs','vci']` |

**Tổng: 3/11 xanh trên bản cũ → 11/11 xanh trên bản mới.**
Lệnh tái lập: script AC chạy với `.env` thật nạp vào `os.environ`.

⚠ **Một test KHÔNG phải bằng chứng đỏ-trước** và được ghi rõ trong docstring:
`test_concat_across_providers_is_a_datetime_not_object` **xanh** trên bản cũ vì
hai frame tổng hợp `[us]`+`[s]` vào `pd.concat` cho `[us]`. Bằng chứng đỏ-trước
của lỗi đơn vị là `test_both_providers_land_on_one_storage_unit`. Điều kiện nào
biến `[us]`+`[s]` thành `object` **chưa cô lập được** — xem `docs/AUDIT_TIER1_WAVE12.md`.

---

## 3. Cổng mới — `check_provider_consistency.py`

Một cổng chỉ chạy xanh thì **chưa** được kiểm. Đã tiêm lại 3 lỗi mà bản cổng cũ
im lặng:

| Lỗi tiêm lại | Exit | Kết quả |
|:--|:--:|:--|
| Bỏ phần nối provider có credential vào cuối | 1 | `C5` bắt |
| Xoá mục `tcbs` khỏi `AUTH_PROVIDERS` | 1 | `C4` bắt |
| Bỏ khoá `env_all` trong cấu hình | 1 | `C0` bắt |
| Cây nguyên bản | 0 | sạch |

`--self-test`: 5 trường hợp âm (TCBS cũ, `env_any` chuỗi, `env_all` chuỗi, thiếu
khoá, mục bị xoá) — tất cả `RED nhu mong doi`, exit 0.

**Không in credential:** cổng chỉ đọc **tên** biến; không có `os.getenv` nào trong
mã cổng; test tiêm một giá trị giả 47 ký tự vào biến mà `env_any` trỏ tới, xác
nhận nó **không** xuất hiện trong output.

---

## 4. Kiểm chứng bằng dữ liệu thật (không chỉ unit test)

Mã `TCB`, ngày 2026-10-10, `.env` thật:

| Kiểm | Kết quả |
|:--|:--|
| `Vnbroker(source='KBS').stock('TCB').quote.intraday()` | 100 dòng · `datetime64[ns, Asia/Ho_Chi_Minh]` · `match_type=['ATC','Buy','Sell']` |
| `Vnbroker(source='VCI').stock('TCB').quote.intraday()` | 100 dòng · `datetime64[ns, Asia/Ho_Chi_Minh]` · `match_type=['ATC','Buy','Sell']` |
| `pd.concat([KBS, VCI])` | **`datetime64[ns, Asia/Ho_Chi_Minh]`**, 200 dòng (trước: `object`) |
| `df[df.match_type=='Buy']` | KBS **74** (trước: **0**) · VCI **67** |
| `Vnbroker(source='TCBS').stock('TCB').quote.history()` | **20 dòng** (trước: `ConnectionError`) |
| `Vnbroker(source='TCBS').stock('TCB').quote.intraday()` | **100 dòng** (trước: `ConnectionError`) |
| `get_auto_candidates('quote')` | `['vci','kbs','dnse','tcbs']` (trước: `['vci','kbs']`) |
| `heatmap_df(['VCB','TCB','BID'])` × 3 `price_unit` | `market_cap` giống hệt, lệch **0.000000%** |
| `BulkAPI.history(['VCB','TCB'])` | 40 dòng · `[ns, Asia/Ho_Chi_Minh]` · `sources_used={'TCB':'KBS','VCB':'VCI'}` |
| `api.quote.Quote(source=…).history/intraday` (KBS & VCI) | cả hai `[ns, Asia/Ho_Chi_Minh]`, `match_type` chuẩn |

**Đối chiếu độc lập:** `VCB` vốn hoá **473 766.78 tỷ VND** =
`56 700 × 8 355 675 094 / 1e9`. Trước đợt này `heatmap_df` trả **473 766 777.83**.

---

## 5. Câu hỏi đã mở từ phiên trước

| Câu hỏi | Kết quả | Bằng chứng |
|:--|:--|:--|
| **Q2** provider trả giá **VND** hay **nghìn VND**? | **VND.** `price_board(price_unit=None)` và `price_board(price_unit='VND')` trả **cùng** `close_price=56700`, `attrs['price_unit']=='VND'`. | Đo live 2026-10-10 |
| **Q3** có được phép probe bằng API key trong `.env` không? | **Không cần.** Q2 chốt được bằng GET-only read-only; **không** gọi write endpoint nào; **không** in giá trị credential nào (chỉ tên + độ dài). | Toàn bộ script đo |
| DNSE ổn định không? | **CHƯA CHẠY — không đo được.** `ConnectionResetError(10054)` 3/3 lần. Tầng socket: TLS handshake tới `openapi.dnse.com.vn` **timeout**; `api.dnse.com.vn` + `ws-openapi.dnse.com.vn` TLS **OK**. | `socket.create_connection` + `ssl.wrap_socket` |
| TCBS ổn định không? | **Có** — sau khi sửa 5 lỗi trong chuỗi. `history` 20 dòng, `intraday` 100 dòng. Nhưng `intraday` **không có** side: server trả `"a": ""` cho mọi bản ghi. | Đo live + raw response |

---

## 6. KHÔNG CHẠY (không phải PASS)

| Hạng mục | Lý do |
|:--|:--|
| CI GitHub Actions | Job bị từ chối khởi động do billing. **Chưa từng chạy.** Mọi gate phải chạy local. |
| Đối chiếu `market_cap` bằng provider thứ hai | `screener` của VCI **và** KBS trả **0 dòng** với các tham số đã thử (`stock(limit=50/1000)`, `stock(params={'symbols': [...]})`). Không có nguồn độc lập để so. Lệnh và kết quả đã ghi ở `docs/AUDIT_TIER1_WAVE12.md` §5 O3. |
| Benchmark hiệu năng AUTO | Chưa có. Vì thế provider có credential **nối cuối**, không lên đầu. |
| DNSE market data | TLS timeout ở tầng socket, không sửa được từ mã thư viện. |
| `vnbroker/broker/**` (write, tiền thật) | Ngoài phạm vi đợt này. **Không** gọi write endpoint nào. |

---

## 7. Số liệu chưa có cùng điều kiện (L-E07)

Baseline `pytest tests/` **do chính tôi đo** ở `9d5db1d` là **không có**: lần đầu
tôi chạy `-Quick` nên `pytest-full` bị skip. Hai con số do phiên trước báo —
`1919 passed / 30 skipped` và `1923 passed / 26 skipped` — **mâu thuẫn nhau**, và
không có lệnh tái lập. Vì vậy báo cáo này **không** tuyên bố "tăng N test so với
trước"; nó chỉ nêu số đo được của cây hiện tại: **1978 passed / 26 skipped**.

Số test mới thêm, đếm bằng `pytest --collect-only`:

| File | Số test |
|:--|--:|
| `tests/contract/test_normalizer_contract.py` | 19 |
| `tests/unit/api/test_snapshot_market_cap.py` | 7 |
| `tests/unit/explorer/test_tcbs_auth_env.py` | 10 |
| `tests/unit/core/test_auto_candidates.py` | 8 |
| `tests/unit/api/test_tcbs_stock_facade_token.py` | 6 |
| **Tổng file mới** | **50** |
| Sửa `test_provider_pool.py` | +4 (thêm 3 ca, đổi 1) |
| Sửa `test_tcbs_auth_token.py` | +1 |
| Sửa `test_stock_ssi.py` | +0 (cập nhật kỳ vọng) |

Cột "contract 91" so với 72 ở baseline: **+19** đúng bằng file hợp đồng mới.