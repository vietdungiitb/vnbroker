# Kế hoạch cải tiến vnbroker (phạm vi: riêng repo này, không liên quan vninvest)

- **Ngày lập:** 2026-09-23
- **Nguồn:** audit nội bộ + phản biện ngoài (5 contradictions doc↔code đã xác minh) + tồn đọng sau commit SSI explorer `496c9ec`
- **Nguyên tắc:** single source of truth cho version (runtime đã dùng `importlib.metadata` từ `pyproject.toml`
  — `core/utils/upgrade.py:74`); mọi tài liệu khác chỉ được **suy ra**, không tự khai version

---

## W1. Chốt single source of truth cho version (P0 — làm trước, 0.5 ngày)

**Hiện trạng (đã xác minh):**

| Nơi khai version | Giá trị | File:line |
|---|---|---|
| `pyproject.toml` (thật, runtime dùng) | `3.3.0` | `pyproject.toml:7` |
| `config.py` `VERSION_REQUIREMENTS/NOTICES/PYTHON_VERSION_SUPPORT` | `3.3.0` | `config.py:62-81` |
| `CHANGELOG.md` | đã có `3.3.0` | `CHANGELOG.md:5` |
| `README.md` | `v3.1.0` ❌ stale | `README.md:5` |
| `CLAUDE.md` | `Current version: 3.1.0` ❌ stale | `CLAUDE.md:260` |

**Yêu cầu:**

1. Sửa `README.md:5` → `v3.3.0` (+ ghi chú `v3.4-dev` trên nhánh `dev`).
2. Sửa `CLAUDE.md:260` → `3.3.0`; rà soát `CLAUDE.md` các số version khác (`v3.1.0`, `v3.1.1` ở §Deprecated — giữ lại vì là lịch sử, nhưng dòng "Current version" phải đúng).
3. Thêm script `scripts/check_version_sync.py`: parse `pyproject.toml:version`, assert khớp với
   `README.md` (regex `vX.Y.Z` dòng đầu), `CLAUDE.md` (`Current version: X.Y.Z`),
   keys của `VERSION_REQUIREMENTS` trong `config.py`. Exit ≠ 0 khi lệch.
4. Gọi script trong `code-quality.yml` (cùng chỗ `check_mypy_baseline.py`).

**AC-W1:** script pass; `grep -rn "3\.1\.0" README.md CLAUDE.md` chỉ còn ngữ cảnh lịch sử
(Deprecated/Changelog), không còn dòng nào tự xưng "current".

## W2. Release hygiene: tags + main/dev (P0 — 1 ngày, chủ repo)

**Hiện trạng:** tags remote chỉ `v1.1.0`, `v3.4.0-core`, `internal-core-1.0.0`
(`git ls-remote --tags origin`); `main=c97f4d4` (tương đương 3.1.x), `dev=496c9ec` (v3.4-dev).

**Yêu cầu:**

1. Tags (quyết định 2026-09-23 sau `git show 38eec3a`): commit duy nhất `38eec3a`
   gộp cả scope 3.2.0 (SSI lane) + 3.3.0 (Retail/UI) nên **không tách 2 tags** →
   chỉ tạo `v3.3.0` tại `38eec3a`, message tag ghi rõ supersede scope v3.2.0
   (`v3.2.0` không phát hành riêng). Không rewrite history để tách.
2. Tag `v3.3.0` kèm GitHub Release ghi breaking changes: xóa MSN/FMP/AUTO+GATEWAY,
   signature `stock(symbol, source)`, TCBS auth chuyển sang env, deps mới
   (`websockets>=12.0`, `cryptography`) + migration snippet 5 dòng.
3. Quy tắc going-forward (ghi vào `CONTRIBUTING` hoặc `CLAUDE.md`): **mọi merge vào `main`
   phải kèm tag `vX.Y.Z`**; `dev` được phép trôi nhưng release notes draft luôn mở.
4. Khi `dev` (hiện `496c9ec`) ổn định: tag `v3.4.0` (gồm price-unit matrix, registry merge,
   HealthStore persistent, Binance crypto, SSI explorer lane).

**AC-W2:** `git ls-remote --tags origin` có `v3.3.0` (message ghi supersede v3.2.0); tag có Release notes chứa mục Breaking.

## W3. Đính chính doc stale (P1 — 0.5 ngày, làm cùng W1)

| # | Sửa | AC |
|---|---|---|
| W3-1 | `README.md:43` "DNSE Company/Finance trả rỗng" → ghi đúng: provider trả rỗng, **facade fallback sang KBS** (`Finance` hard-fallback `data.py:969-976`; `Company` empty-skip `data.py:269-274`); khuyên assert `attrs["source_used"]` | Câu chữ khớp behavior facade, có ví dụ 3 dòng |
| W3-2 | `TODO.md:19` tick crypto → sửa thành "crypto (Binance) xong; **fx/world_index vẫn `NotImplementedError`** (`client.py:139-205`)" | Không ai đọc nhầm "xong hết" nữa |
| W3-3 | `docs/SSI_USAGE_GUIDE.md` §5 đã thêm (commit `496c9ec`); rà 1 lượt các guide `TCBS_*/RETAIL_USAGE` còn số version cũ | grep version cũ trong `docs/` chỉ còn lịch sử |

## W4. Quality gates: đóng vòng mypy/ruff (P1 — 1 ngày)

**Hiện trạng:** CI có `check_mypy_baseline.py` (baseline 552 lỗi strict, expiry 2026-12-31) +
`code-quality.yml`; nhưng môi trường dev offline không cài được mypy/ruff qua pip
(đã gặp khi implement SSI lane — phải thay bằng `py_compile` + grep, kém chặt).

**Yêu cầu:**

1. Khai báo `mypy` + `ruff` vào dev extras (`pyproject.toml` hoặc `pyproject.toml.testing` —
   kiểm tra hiện có chưa; thiếu thì thêm, pin version).
2. Tài liệu hóa offline fallback trong `CLAUDE.md` (Development Workflow):
   khi không cài được tool → `py_compile` + grep checklist, **ghi rõ trong PR** để CI chạy bù.
3. Lên lịch shrink baseline trước expiry 2026-12-31: mỗi PR chạm file nào thì fix hết lỗi strict
   file đó (quy tắc đã có trong header script — thực thi, không chỉ ghi).
4. Chạy bù cho commit `496c9ec`: `mypy vnbroker/explorer/ssi ... --strict` +
   `ruff check/format` trên CI; nếu đỏ thì fix-forward 1 commit riêng (không revert cả lane).

**AC-W4:** CI `code-quality.yml` xanh trên `dev`; baseline không tăng (so `mypy-baseline.txt`).

## W5. Close-out SSI explorer lane `496c9ec` (P1 — chờ key, 0.5 ngày khi có)

1. Người giữ key SSI chạy: `vnbroker_RUN_LIVE_INTEGRATION=1 pytest tests/integration/explorer/test_ssi_live.py -v`
   (3 case đã viết). Log redact secret, lưu đè `artifacts/ssi_explorer/live_ssi.log`.
2. Nếu live fail do spec server khác kỳ vọng → fix-forward mapping (không đổi contract 17 cột
   trừ khi có bằng chứng server).
3. Xong thì đánh dấu E-6 trong `review_checklist.md` và close task.

**AC-W5:** `live_ssi.log` 3 passed, không secret trong log.

## W6. Tài liệu vận hành HealthStore cho consumer (P2 — 0.5 ngày, vẫn phía vnbroker)

**Hiện trạng:** default `~/.vnbroker/router_health.sqlite3`, override `vnbroker_ROUTER_HEALTH_DB`
(`core/health_store.py:138-154`); không có Redis backend. Consumer chạy container sẽ mất state
khi restart nếu không biết.

**Yêu cầu:** thêm mục vào `docs/AUTO_SOURCE_GUIDE.md` (hoặc README): nơi lưu default,
cách trỏ env sang volume persistent, khuyến nghị TTL/cooldown vận hành, nêu rõ "không Redis".

**AC-W6:** đọc guide xong, người vận hành tự cấu hình persistent được không cần hỏi.

---

## Thứ tự thực hiện và effort

| Thứ tự | Việc | Effort | Phụ thuộc |
|---|---|---|---|
| 1 | W1 (version sync + script + CI) | 0.5 ngày | — |
| 2 | W3 (đính chính doc) | 0.5 ngày | W1 (dùng chung quy tắc version) |
| 3 | W2 (tags + releases) | 1 ngày | W1 (số version chốt) |
| 4 | W4 (dev extras + CI bù 496c9ec) | 1 ngày | — (song song được) |
| 5 | W5 (live SSI, khi có key) | 0.5 ngày | W4 |
| 6 | W6 (HealthStore guide) | 0.5 ngày | — |

Tổng ~4 ngày công, không phụ thuộc vninvest ở bất kỳ bước nào.
