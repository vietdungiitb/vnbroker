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

| Agent | Branch | Phạm vi | File sẽ sửa |
|---|---|---|---|
| **a1** | `feat/a1-bars` | GĐ1 — nối `bars` | `explorer/tcbs/bars.py` (mới), `explorer/tcbs/quote.py`, test mới |
| **a2** | `feat/a2-ws` | GĐ2 — viết lại WebSocket | `explorer/tcbs/websocket.py`, `ws_models.py`, test mới |
| **a3** | `feat/a3-legacy` | GĐ3 — xoá path legacy | `broker/tcbs/account.py`, `broker/tcbs/equity.py`, test mới |

**Kiểm tra rời nhau:** `quote.py`/`bars.py` ∩ `websocket.py`/`ws_models.py` ∩
`account.py`/`equity.py` = **∅**. Không agent nào chạm file của agent khác.

---

## 3. Tiêu chí chấp nhận (Given/When/Then)

### S1 — a1

| # | AC |
|---|---|
| 1 | **Given** response thật của `bars-long-term`, **when** parse, **then** frame có đúng cột `time, open, high, low, close, volume` |
| 2 | `time` **tz-aware `Asia/Ho_Chi_Minh`** — KHÔNG phải UTC (bẫy đã đo: `Normalizer` giữ UTC) |
| 3 | `2025-09-12T00:00:00Z` → `2025-09-12 07:00:00+07:00`, **ngày không dịch** |
| 4 | `dataT1: null` (field không có trong spec) **không** gây lỗi, **không** lọt vào frame |
| 5 | `history(interval='1D', start≠end)` **không** còn ném `NotImplementedError` |
| 6 | Docstring sai ở `quote.py:347` và `:421` đã sửa |
| 7 | `bars` và `bars-long-term` phân biệt đúng: `1D/1W/1M` → long-term; `1m/5m…` → intraday |
| 8 | **`quote.py` không vượt 800L** sau thay đổi |

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
| 8 | Test **offline** với frame thật lấy từ tài liệu — **không cần mạng** |

### S3 — a3

| # | AC |
|---|---|
| 1 | 19 path legacy bị xoá khỏi `_PATHS` |
| 2 | **Không** còn path `erebos/v1`, `erebos/v2`, `aion/v1/accounts` (không path param) trong mã |
| 3 | Method công khai gọi path đó **ném lỗi rõ ràng**, không im lặng trả rỗng |
| 4 | `account.py` và `equity.py` **≤800L** sau khi xoá |
| 5 | 35 path còn lại **không đổi** — contract test chứng minh |

---

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
