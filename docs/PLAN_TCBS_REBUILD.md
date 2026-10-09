# PLAN — TCBS Rebuild (Giai đoạn 1–3)

**Base:** `dev @ bec8b82` · **Ngày:** 2026-10-09 · **Mode A (delegation), 3 worker**
**Nguồn:** `docs/PROPOSAL_TCBS_REBUILD_20261009.md`, `docs/AUDIT_TCBS_OPENAPI_20261009.md`
**Căn cứ đối chiếu:** `developers.tcbs.com.vn/docs/v1.0.0/*`, `/specs/openapi-v1.0.0.json`,
`/specs/tcbs-openapi-v1.0.0.postman_collection.json`

---

## 0. Baseline gate — đo tại `bec8b82`, **không ước lượng** (hazard 6)

| Gate | Lệnh | Exit | Kết quả |
|---|---|---|---|
| pytest toàn bộ | `.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider` | **0** | `1497 passed, 26 skipped` |
| ruff src | `.venv\Scripts\python.exe -m ruff check vnbroker` | **0** | `All checks passed!` |
| mypy | `.venv\Scripts\python.exe scripts/check_mypy_baseline.py` | **0** | `no new strict errors (baseline 1266, now 1207)` |
| ruff tests | `… -m ruff check tests` | **1** | ⚠ **13 lỗi KNOWN-RED có sẵn** — không được đòi PASS |
| ngân sách file | đếm `>800L` | — | ⚠ **13 file vượt, 4 thuộc TCBS** |

> Gate `ruff tests` đang **đỏ sẵn**. Kế hoạch này **không** đòi nó xanh; chỉ đòi
> không tăng thêm. `CLAUDE.md:15` — "800 max".

---

## 1. Ràng buộc phát hiện ở Stage 1

`quote.py` đang **801L** — thêm code sẽ phá ngân sách. ⇒ S1 **không** viết thẳng vào
`quote.py` mà tách module mới `explorer/tcbs/bars.py`, `quote.py` chỉ ủy nhiệm.

---

## 2. Slicing — ba lát **không chung file** (§0.5)

> **KẾT QUẢ 2026-10-09 — cả 3 lát DONE, đã merge vào `dev`.**
> `a1` → `6c88f4b` · `a2` → `f2ba384` · `a3` → `de4c7f8` · fix fixture của
> coordinator → `a832a84`. Gate: `1696 passed / 26 skipped` (baseline 1497 ⇒
> **+199**), mypy baseline 1266→1161, contract 72, ruff exit 0.
> Bàn giao tổng: `docs/SUMMARY_TCBS_REBUILD.md`.
> **Còn nợ:** GĐ4 TokenManager, GĐ5 13 endpoint, `derivatives.py` 852L.

| Agent | Branch | Phạm vi | File sẽ sửa |
|---|---|---|---|
| **a1** ✅ | `feat/a1-bars` | GĐ1 — nối `bars` | `explorer/tcbs/bars.py` (mới), `explorer/tcbs/quote.py`, test mới |
| **a2** ✅ | `feat/a2-ws` | GĐ2 — viết lại WebSocket | `explorer/tcbs/websocket.py`, `ws_models.py`, `explorer/tcbs/stream.py`, `tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py` (mới) |
| **a3** ✅ | `feat/a3-legacy` | GĐ3 — xoá path legacy | `broker/tcbs/account.py`, `broker/tcbs/equity.py`, `broker/tcbs/client.py`, `brokerage/tcbs/client.py`, `tests/unit/broker/tcbs/test_tcbs_legacy_removed.py` (mới), `tests/integration/tcbs/test_tcbs_full_acb.py`, `tests/unit/broker/tcbs/test_account_money.py`, `tests/unit/broker/tcbs/test_equity_derivatives.py` |

**Kiểm tra rời nhau:** `quote.py`/`bars.py` ∩ `websocket.py`/`ws_models.py` ∩
`account.py`/`equity.py` = **∅**. Không agent nào chạm file của agent khác.

> **ĐÍNH CHÍNH sau audit độc lập (2026-10-09).** Tiêu chí "legacy" trong lát a3
> ban đầu được phát biểu là *"path có tiền tố `erebos`/`aion`"*. **Sai**: spec
> chính thức có các endpoint đúng các tiền tố đó (`money.py` giữ 2 path
> `/erebos/v2/digital/*`, đều **có** trong spec lẫn Postman). Tiêu chí đúng là
> **vắng ở path cụ thể**, đã xác minh riêng từng cái (18/18 vắng).

---

## 3. Tiêu chí chấp nhận (Given/When/Then)

### S1 — a1

| # | AC |
|---|---|
| 1 | **Given** response thật của `bars-long-term`, **when** parse, **then** frame có đúng cột `time, open, high, low, close, volume` |
| 2 | `time` **tz-aware `Asia/Ho_Chi_Minh`**. Bắt buộc gọi `tz_convert` **tường minh** — `Normalizer` chỉ `tz_localize` khi chưa có tz nên giữ nguyên UTC. Kiểm tz ở **tầng data**, sau `Normalizer` |
| 3 | `2025-09-12T00:00:00Z` → `2025-09-12 07:00:00+07:00`, **ngày giao dịch không dịch** |
| 4 | **Mọi field không có trong spec phải `.get()` an toàn.** Quan sát thật: response còn trả `dataT1: null`, không có trong cả 2 tài liệu — AC này về **nguyên tắc**, không về tên field. Frame chỉ chứa cột chuẩn |
| 5 | `history(interval='1D', start≠end)` **không** còn ném `NotImplementedError` |
| 6 | Docstring sai ở `quote.py` (~dòng 347 và ~421) đã sửa thành mô tả đúng |
| 7 | Phân biệt đúng `bars` vs `bars-long-term`. **Map `D/W/M` riêng trong `bars.py`** — **không** dùng `_INTERVAL_MAP` (`const.py:19`) vì nó map `1M → 'ME'` (pandas), spec TCBS quy định `resolution: D \| W \| M` |
| 8 | Chuyển `_TIMEFRAME_MAP` từ `quote.py:46-55` sang `const.py` để tránh **circular import** `bars.py ↔ quote.py` |
| 9 | **`bars.py` không đi qua `_as_df`/`ohlc_to_df`** — `transform.py:402,406` **cắt tz và cắt giờ**, làm AC#3 không khả thi. Phải `tz_convert` tường minh rồi mới đưa qua `Normalizer` |
| 10 | **`quote.py` ≤ 800L** sau thay đổi (`CLAUDE.md:15`) |

### S2 — a2

| # | AC |
|---|---|
| 1 | Auth gửi **text frame** `d\|a\|\|\|<base64(token)>`, **không** phải header HTTP |
| 2 | **Chờ** `d\|0\|{"success":true}` trước khi subscribe |
| 3 | Subscribe `d\|s\|tk\|bp+bi+tm+mp+op+fe\|<SYMBOLS>`; unsubscribe `d\|u\|…` |
| 4 | Heartbeat `d\|p\|\|\|` mỗi 2s; đọc `d\|33\|15` |
| 5 | Parse `s\|<CHANNEL>\|<JSON>`; **giữ nguyên văn bản thô**, không `json.loads(toàn bộ)` |
| 6 | `thesis/normal` và `thesis/derivative` có **channel ID riêng** — không dùng chung parser |
| 7 | Xoá `_WS_ENDPOINTS_SIT` (host không tồn tại, DNS FAIL đã đo) |
| 8 | Test **offline** với frame thật lấy từ tài liệu — **không cần mạng**, không gọi network |
| 9 | **Giữ tương thích `stream.py`** — `use_sit`, tên channel, chữ ký `subscribe`. `stream.py:11,18,47,68,71,89,109,129,150` gọi thẳng `websocket.py`/`ws_models.py` và **hiện có 0 test** ⇒ hỏng ở đây sẽ im lặng |

### S3 — a3

| # | AC |
|---|---|
| 1 | 19 path legacy bị xoá khỏi `_PATHS` |
| 2 | **Không** còn path `erebos/v1`, `erebos/v2`, `aion/v1/accounts` (không path param) trong mã |
| 3 | Method công khai gọi path đó **ném lỗi rõ ràng**, không im lặng trả rỗng |
| 4 | `account.py` và `equity.py` **≤800L** sau khi xoá |
| 5 | 37 path còn lại **không đổi** — contract test chứng minh |
| 6 | `get_account_list` là `@abstractmethod` (`brokerage/base.py:55`) ⇒ xoá `/aion/v1/accounts` **không được** phá vỡ hợp đồng. Không tìm được nguồn thay thế trong spec thì **giữ lại** và ghi là ngoại lệ |
| 7 | 17 wrapper trong `brokerage/tcbs/client.py:161-241,395-430` và `broker/tcbs/client.py` (102 dòng) gọi method bị xoá ⇒ phải sửa hoặc bỏ, **không** để lỡ |

---

## 3b. Rủi ro **đã biết** — đọc trước khi code

| # | Rủi ro | Bằng chứng | Hệ quả |
|---|---|---|---|
| R1 | **Xoá 19 path legacy là quyết định của Owner theo 2 tài liệu, CHƯA probe server.** `401` chạy trước routing nên không phân biệt được route có hay không; môi trường SIT `openapisit.tcbs.com.vn` **DNS FAIL** (đã đo) nên không có cách nào verify | `git log -S 488b082e`; probe `405` cần auth | Nếu TCBS vẫn phục vụ ⇒ mất chức năng tiền thật. Vì vậy AC S3#3 bắt buộc **ném lỗi rõ ràng**, không trả rỗng |
| R2 | Số "37 path còn lại" là **đo bằng script AST + so khớp chuẩn hoá**, tái lập bằng `docs/AUDIT_TCBS_OPENAPI_20261009.md`. Tôi từng ghi "35" — sai | script trong §0 | Nếu con số lệch, AC S3#5 sai theo |
| R3 | Không có token hợp lệ ⇒ **không verify live được** trong đợt này | `apikey/info` 200 nhưng `.env` chứa API key, không phải JWT; cần Smart OTP | Mọi kết luận "đúng theo spec" phải ghi kèm, không báo PASS |

> **Không được viết "đã xác nhận path không tồn tại".** Chỉ được viết:
> *"xoá theo quyết định Owner, dựa trên 2 tài liệu chính thức, chưa probe server."*

## 4. Ngoài phạm vi (không làm)

- GĐ4 TokenManager · GĐ5 13 endpoint còn lại — lát sau
- Viết lại `broker/tcbs/derivatives.py` (852L) — ngoài lát này
- Xoá `_analysis`/`_stocks`/`_future` URLs của domain cũ — ghi nhận, chưa đụng

---

## 5. Rollback

Mỗi lát là một branch độc lập, revert được riêng:
```bash
git revert <merge-sha>          # hoặc
git branch -D feat/a1-bars      # trước khi merge
```

---

## 6. Nguyên tắc bắt buộc cho cả 3 agent

1. **Không** dùng `git checkout -- <file>` để thử nghiệm (hazard 11) — dùng
   `git show HEAD:<file> > <file>` sau khi copy file ra ngoài.
2. **Không** dùng `--no-verify`.
3. Mọi test mới phải chứng minh **fail trước, pass sau** (hazard 10).
4. Số liệu trong `docs/SUMMARY_*.md` phải kèm lệnh tái lập được.
5. File không có dấu: đọc bằng `Get-Content -Encoding utf8` (hazard 5).
6. Agent ghi `docs/SUMMARY_<agent>.md` **trước khi** supervisor hành động.


