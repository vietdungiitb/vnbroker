# EVIDENCE — Fix P0 corporate_actions `ex_date=None` (2026-11-20)

- **Scope**: lỗi P0 phát hiện khi vninvest re-probe `vnbroker==3.8.1`
  (`vninvest/docs/evidence/corporate-actions/REPROBE_VNBROKER_381_20261120.md`).
- **Base**: `vnbroker@main@99dabbe` · branch `fix/corporate-actions-exrightdate`.
- **Owner fix**: vnbroker. **Owner bump pin**: vninvest (sau release 3.8.2).

## 1. Findings (file:line)

| # | Phát hiện | Evidence |
|---|---|---|
| F1 | Raw key thật của VCI là `exrightDate` (chữ `r` thường), 57/57 event có key này, giá trị ISO `YYYY-MM-DDT00:00:00` | probe live VNM; fixture `tests/fixtures/vci_news_events_vnm_20261120.json` |
| F2 | `vnbroker/common/corporate_actions.py:155` (3.8.1) chỉ `_pick("exright_date", "exRightDate", "ex_date")` ⇒ `ex_date=None` 100% | nhìn thẳng source + chạy fixture |
| F3 | `vnbroker/common/corporate_actions.py:183` tạo `group_id=f"{symbol}:{ex_date}"` ⇒ `VNM:None` cho mọi dòng | probe fixture (E1) |
| F4 | Endpoint trả 1057 dòng = 57 event + 1000 news (`isEvent=False`, không `eventCode`); normalizer cũ trả hết vào contract | probe live + fixture 77 dòng |
| F5 | `events()` không bị lỗi vì snake_case ở `vnbroker/explorer/vci/company.py:310-315`; pipeline vninvest dùng legacy này ⇒ không breaking | source + re-probe vninvest |

## 2. Reproduce (lệnh thật)

```powershell
# E1 — fail-before trên code 3.8.1 (fixture trong repo, không cần mạng)
python -c "import json,pathlib; from vnbroker.common.corporate_actions import normalize_events as n; r=json.loads(pathlib.Path('tests/fixtures/vci_news_events_vnm_20261120.json').read_text(encoding='utf-8')); d=n(r,'VNM'); print(len(d), int(d['ex_date'].isna().sum()), sorted(set(d['group_id']))[:1])"
# 77 77 ['VNM:None']

# E2 — fail-before test (trước fix): 5 failed, 1 passed
python -m pytest tests/unit/common/test_corporate_actions_parser.py -q -k RealVCI

# E3 — pass-after (sau fix): 25 passed cho 3 file slice
python -m pytest tests/unit/common/test_corporate_actions_parser.py tests/unit/explorer/test_vci_corporate_actions.py tests/unit/api/test_corporate_actions_api.py -q
# 25 passed in 9.47s
```

**Live probe sau fix** (`Company(...).corporate_actions(from_date='20100101', to_date='20261120')`):

| Mã | dòng trả | `ex_date=None` | `action_type` | `group_id` | 2024-09-24 |
|---|---:|---:|---|---:|---:|
| VNM | 57 | 0 | DIV, ISS | 48 | 2 |
| FPT | 79 | 0 | DIV, ISS | 57 | 0 |
| VCB | 23 | 0 | DIV, ISS | 20 | 0 |

Facade `vnbroker.api.company.Company(source='VCI', symbol='VNM').corporate_actions()` →
**57 dòng, source=VCI, ex_date đầu tiên 2010-02-09, 0 dòng None**.

## 3. Impact & root cause

- **Impact (P0)**: mọi consumer chuyển sang API có cấu trúc sẽ gom nhầm toàn bộ sự kiện
  vào một `group_id`, làm vô nghĩa phép so sánh cùng `ex_date` (R3) và có thể tính sai
  hệ số điều chỉnh giá nếu dedup theo ngày. 1000 dòng news lẫn vào contract gây
  `action_type=''`/`parse_status='unparsed'` nhiễu.
- **Không ảnh hưởng pipeline vninvest hiện tại**: vẫn dùng legacy `events()` + parser riêng,
  tự lọc `exright_date`/`event_code` (`REPROBE_VNBROKER_381_20261120.md` §4).
- **Root cause**: `corporate_actions()` nhận **raw dict** (camelCase) từ
  `_fetch_news_events()`, nhưng danh sách key trong `_pick` được viết theo camelCase
  sai (`exRightDate`) và normalizer giả định mọi row đều là event.

## 4. Giải pháp + ưu tiên

1. `[P0, đã làm]` Thêm key thật vào `_pick`: `exrightDate`, giữ các key cũ cho tương thích.
2. `[P0, đã làm]` Lọc `_is_event_row()`: bỏ `isEvent=False` (hoặc string false-like)
   và row không có `eventCode`; giữ row cũ chỉ có `eventCode`.
3. `[P1, đã làm]` Golden fixture 57 event VNM + 20 news; assert 57 dòng, 57 `ex_date`,
   2 DIV `2024-09-24` (950 + 1500) giữ riêng. Không dedup, không đổi schema 14 cột.
4. `[P1, XONG 2026-11-20T15:03Z]` Tag + GitHub Release `v3.8.2` xong; publish run
   `44758095521` sau rerun **success**; PyPI JSON `version=3.8.2`, wheel + sdist,
   `yanked=false`, wheel chứa `"exrightDate"` + `_is_event_row`. vninvest giờ mới bump
   pin `3.8.1 → 3.8.2` + re-probe → mới chuyển `ingest.fetch_corporate_actions` sang
   field số. Giữ `CORPORATE_ACTIONS_ENABLED=False` tới khi xong. Lưu ý mirror pip
   nội bộ có thể còn lag: dùng `--index-url https://pypi.org/simple` nếu cần.

## 5. Tests / gates

| Gate | Kết quả |
|---|---|
| Fail-before `-k RealVCI` | **5 failed, 1 passed** (chứng minh đúng lỗi, L-E06) |
| 3 file unit corporate actions | **25 passed** |
| `ruff check` 2 file đổi | `All checks passed!` |
| Live probe VNM/FPT/VCB + facade | ✅ số liệu bảng §2 |
| Full suite `pytest tests/` | **CHƯA CHẠY** (xem report final) |
| CI publish 3.8.2 | **CHƯA CHẠY** — chờ owner tag/release |

## 6. Next steps / owner

- Owner vnbroker: merge branch vào `main`, tag `v3.8.2`, GitHub Release → PyPI.
- Owner vninvest: bump pin + re-probe + (ch sau đó) đổi ingest sang API có cấu trúc;
  mapping `is_esop ↔ ambiguous_ratio_pct` tại `FIELD_MAPPING_VNBROKER.md`.
- Không tự bật `CORPORATE_ACTIONS_ENABLED`.
