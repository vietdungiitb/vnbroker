# PLAN — Fix P0 `ex_date=None` + news rows trong corporate_actions (2026-11-20)

- **Branch**: `fix/corporate-actions-exrightdate` · base `main@99dabbe` (3.8.1)
- **Phát hiện từ**: `vninvest/docs/evidence/corporate-actions/REPROBE_VNBROKER_381_20261120.md`
  (re-probe PyPI 3.8.1: VNM 1057 dòng, `ex_date=None` 100%).
- **Lessons áp dụng**: `[L-E01, L-E02, L-E06, L-R01]` (số kèm lệnh; fixture trong repo;
  test fail-before gọi hàm thật; HTTP 200 ≠ dữ liệu đúng).

## 1. Bằng chứng (tự đo, không tin tài liệu)

| # | Sự thật | Nguồn / lệnh |
|---|---|---|
| E1 | Raw key VCI là `exrightDate` (chữ `r` thường), kiểu ISO string `2010-02-09T00:00:00` | probe live VNM, 57/57 event có key này |
| E2 | `_pick` chỉ nhận `exright_date`, `exRightDate`, `ex_date` ⇒ trượt key thật | `vnbroker/common/corporate_actions.py:155` |
| E3 | 57 event + 1000 news (`isEvent=False`, không `eventCode`) trong cùng payload | probe live: `rows=1057`, `events=57` |
| E4 | Code cũ trả 77/77 dòng `ex_date=None`, `group_id='VNM:None'` | chạy fixture cũ trước fix (mục 4) |

Tái tạo fixture (đã commit, không gọi mạng khi test):

```powershell
python -c "..."  # xem docs/evidence/CORPORATE_ACTIONS_FIX_381_EVIDENCE_20261120.md
```

## 2. Nguyên nhân gốc

1. `normalize_events()` nhận **raw dict** từ `_fetch_news_events()` (camelCase), khác
   `events()` đã snake_case (`vnbroker/explorer/vci/company.py:310-315`). Danh sách key
   trong `_pick` được viết theo giả định `exRightDate` (viết hoa chữ R) — sai với payload
   thật `exrightDate`.
2. Endpoint `news-events-for-chart` trả lẫn news; normalizer không lọc `isEvent`.

## 3. Phạm vi (SCOPE)

- `vnbroker/common/corporate_actions.py`: thêm key `exrightDate`; lọc news rows.
- `tests/unit/common/test_corporate_actions_parser.py`: test fail-before + golden.
- `tests/fixtures/vci_news_events_vnm_20261120.json`: 57 event thật + 20 news (fixture).
- Docs evidence + plan + report.
- (Commit riêng, coordinator) bump `3.8.1 → 3.8.2`: `pyproject.toml`, `README.md`,
  `CLAUDE.md`, `vnbroker/config.py`, `CHANGELOG.md`.

**Non-goals**: không đổi `events()` / contract cũ; không đổi schema 14 cột; không sửa
`ingest` phía vninvest; không bật flag `CORPORATE_ACTIONS_ENABLED`; không dedup 2 DIV
cùng `ex_date`.

**LIMIT**: tối đa 3 vòng fail→fix. Rollback: revert commit fix; 3.8.1 vẫn nguyên trên PyPI.

## 4. Tiêu chí nghiệm thu (Given/When/Then)

- **AC-1**: Given raw row có `exrightDate='2024-09-24T00:00:00'`, When normalize, Then
  `ex_date='2024-09-24'` và `group_id='VNM:2024-09-24'`.
- **AC-2**: Given payload 57 event + 20 news, When normalize, Then đúng **57 dòng**,
  `action_type` ⊆ {DIV, ISS}, không dòng nào rỗng.
- **AC-3**: Given golden VNM, Then 2 dòng `2024-09-24` giữ riêng với `cash_amount`
  950 và 1500, `source_event_id` khác nhau.
- **AC-4**: Given `isEvent=False` / thiếu `eventCode`, Then bị loại; `isEvent` vắng mặt
  nhưng có `eventCode` (payload cũ) vẫn được giữ.
- **AC-5**: 57/57 event có `ex_date` khác None.

## 5. Baseline cổng (trước fix)

| Gate | Lệnh | Kết quả |
|---|---|---|
| Parser tests | `python -m pytest tests/unit/common/test_corporate_actions_parser.py tests/unit/explorer/test_vci_corporate_actions.py tests/unit/api/test_corporate_actions_api.py -q` | xem RUN log |
| Fixture repro | `normalize_events(fixture,'VNM')` | **77 dòng, 77 None, group `VNM:None`** |
| `check_version_sync` | `python scripts/check_version_sync.py` | sau bump |

## 6. Thứ tự thực thi

1. Viết test mới → chạy **đỏ** trên code cũ (dán output).
2. Sửa `_pick` + filter → chạy **xanh**.
3. Ruff + full targeted suite + `check_version_sync` sau bump.
4. Evidence doc + report + ledger/claim đóng; merge `main`; tag/release 3.8.2 (owner gate).
