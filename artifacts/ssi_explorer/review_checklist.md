# Review checklist — SSI Explorer (reviewer đánh từng ô, 1 ô fail = trả về)

- [x] Mỗi FR ở §4 có ít nhất 1 test ở §7.2 trỏ tới.
  Minh chứng: FR-Q1→`test_quote.py::TestSSIQuoteHistory`; FR-Q2→`TestSSIQuoteUnsupported`;
  FR-L1→`test_listing.py`; FR-T1→`test_trading.py`; FR-C1/F1/N1→`test_company/financial/news.py`;
  FR-W1→`test_stock_ssi.py` + `test_registry.py` + `test_ssi_source.py`; FR-W2→`test_auth.py`.
- [x] Message lỗi đúng câu chữ §4 (so sánh chuỗi trong test):
  `SSI cần api_key` (init cả 6 providers), sai date `YYYY-MM-DD`, `30m` NotImplementedError,
  interval lạ `ValueError`, intraday/depth chứa `KBS`+`VCI`+`stream`.
- [x] Schema assert bằng `list(df.columns)`: history 6 cột (+`value` khi get_all);
  listing 2 cột / group `Series(symbol)`; price_board đúng 17 cột tên KBS;
  company/finance/news rỗng đúng cột DNSE.
- [x] `attrs` đủ key ở history/price_board/news-fallback (assert key trong test).
- [x] NFR-1/2: **LỆCH MÔI TRƯỜNG** — `mypy`/`ruff` không cài được trong venv này
  (`pip install` không mạng). Thay thế: `py_compile` toàn bộ 32 file chạm (pass),
  grep `print(` = rỗng, grep `core.utils.client` = rỗng, grep secret-trong-logger = rỗng.
  **CI phải chạy lại lệnh §8.2 mục 5 trước khi merge.**
- [x] Không sửa logic nhánh VCI/KBS/TCBS/DNSE: diff chỉ `+` thêm `"ssi"`/params key;
  ngoại lệ đúng như NFR-8 (`types.py` enum, `constants.py` attr, `PUBLIC_VN_SOURCES`,
  `_annotate_news_fallback` dùng `self.source`, 5 `valid_sources` api/).
  File `.env` không có trong diff.
- [x] Docs: `SSI_USAGE_GUIDE.md` §5 (SSI-source + ma trận native-vs-fallback);
  mọi public method có Google-style docstring.
- [x] E-6 live: **SKIP có lý do** — môi trường này không có key SSI thật
  (`.env` chỉ có DNSE). Người giữ key chạy `test_ssi_live.py` gated trước khi close.
