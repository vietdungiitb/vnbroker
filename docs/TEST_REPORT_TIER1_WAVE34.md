# TEST REPORT — Tier-1 Wave 3 + Wave 4

**Ngày:** 2026-10-10 · **HEAD:** xem §1 · **Máy:** Windows, `.venv` của repo

⚠ **Mọi dòng dưới đây là kết quả CHẠY THẬT trên máy này.** Dòng nào không chạy
đều ghi `CHƯA CHẠY` kèm lý do — không có dòng "chắc là xanh".

---

## 1. Cổng tổng thể

| # | Cổng | Lệnh thật | Exit | Kết quả |
|:--|:--|:--|:-:|:--|
| 1 | **check_all** | `pwsh -File scripts/check_all.ps1` | **0** | 9 PASS · 1 KNOWN-RED · 0 FAIL |
| 2 | ruff src | `python -m ruff check vnbroker scripts tests/unit tests/contract` | **0** | `All checks passed!` |
| 3 | ruff tests-all | `python -m ruff check tests` | **1** | `Found 13 errors` — **KNOWN-RED**, có sẵn từ `9d5db1d` (nợ N3) |
| 4 | version-sync | `python scripts/check_version_sync.py` | **0** | `version-sync OK: 3.7.0` |
| 5 | lessons | `python scripts/check_lessons.py` | **0** | `24/40 lesson · 5 file - sach` |
| 6 | tcbs-coverage | `python scripts/verify_tcbs_coverage.py` | **0** | `spec sha256 7f97d27b…42bd4a (KHOOP)` |
| 7 | tcbs-bodies | `python scripts/check_tcbs_bodies.py --baseline docs/tcbs_body_baseline.json` | **0** | `lech da biet (baseline): 0` |
| 8 | provider-consistency | `python scripts/check_provider_consistency.py` | **0** | `OK: khong co vi pham nao.` |
| 9 | mypy baseline | `python scripts/check_mypy_baseline.py` | **0** | `no new strict errors (baseline 1266, now 1138, fixed 128)` |
| 10 | contract | `python -m pytest tests/contract -q` | **0** | `91 passed` |
| 11 | toàn bộ | `python -m pytest tests/ -q --timeout=300` | **0** | `2032 passed, 26 skipped, 2 warnings, 3 subtests` |

**Self-test các cổng mới** (do `check_all.ps1` chạy trước): lessons-selftest **PASS**
(9 ca âm) · tcbs-bodies-selftest **PASS** (10 ca âm) · provider-consistency-selftest
**PASS** (5 ca âm).

### 1.1 Số đo trước → sau (cùng một lệnh, cùng một máy)

| Chỉ số | Trước `4cd0f2d` | Sau | Lệnh tái lập |
|:--|:--|:--|:--|
| `pytest tests/ -q` | `1978 passed, 26 skipped` | **`2032 passed, 26 skipped`** | `python -m pytest tests/ -q --timeout=300` |
| contract | `91 passed` | `91 passed` | `python -m pytest tests/contract -q` |
| mypy baseline | `1138` | `1138` (lỗi mới: **0**) | `python scripts/check_mypy_baseline.py` |
| file >800L trong `vnbroker/` | `10` | `10` | `python -c "…rglob('*.py')…len(splitlines())"` |
| `common/data.py` | `1823` dòng | **`1823`** dòng (không dài thêm) | như trên |

---

## 2. AC — trạng thái cuối

| AC | Kết quả | Bằng chứng |
|:--|:--|:--|
| **AC-3.1** cooldown theo `Retry-After` | **PASS** | `Retry-After: 120` ⇒ `cooldown_remaining_sec = 119.93` |
| **AC-3.2** 429 không retry (source cố định) | **PASS** | **1** attempt (base: **3**) |
| **AC-3.3** 429 không retry (AUTO, 2 provider) | **PASS** | **2** attempt (base: **6**) |
| **AC-3.4** failover A→B | **PASS — nhưng xanh sẵn ở base** | `source_used=VCI`, `kbs failures=1`. Đây là **canh gác hồi quy**, **không** phải bằng chứng fix |
| **AC-3.5** `should_failover(RateLimitError)` | **PASS** | `False` (base) → `True` |
| **AC-4.1** không rò token | **PASS** | rò **4/10** (base) → **0/10** |
| **AC-4.2** không phá prose | **PASS — nhưng 5/6 xanh sẵn ở base** | 6/6 không đổi |
| **AC-4.3** `monkey=abc` | **PASS** | base: **bị đổi** → nay giữ nguyên |
| **AC-4.4** dict-arg không mất dòng log | **PASS** | base: `TypeError`, mất dòng → nay `x={'a': 1, 'b': 2}` |
| **AC-4.5** dict-arg chứa Bearer | **PASS** | `x={'Authorization': 'Bearer ***REDACTED***'}` |

### 2.1 Bằng chứng **ĐỎ trước / XANH sau** (hazard 10)

Đây là phần quan trọng nhất: test xanh cả trước và sau thì **bằng chứng = 0**.

| AC | Đo được ở `4cd0f2d` | Đo được sau |
|:--|:--|:--|
| AC-3.1 | `cooldown_remaining_sec = 4.935` (suy đoán) | `119.93` |
| AC-3.2 | **3** attempt | **1** |
| AC-3.3 | **6** attempt | **2** |
| AC-3.5 | `should_failover = False` | `True` |
| AC-4.1 | **4/10** rò | **0/10** |
| AC-4.3 | `'monkey=abc'` → `'monkey: "***REDACTED***"'` | `'monkey=abc'` |
| AC-4.4 | `TypeError` ⇒ **mất dòng log** | dòng log còn |
| AC-4.5 | dòng log `x=Authorization` (giá trị mất) | `x={'Authorization': 'Bearer ***REDACTED***'}` |

⚠ **Hai AC xanh sẵn ở base** (`AC-3.4`, `AC-4.2` 5/6 chuỗi). Chúng **giữ** để
chặn hồi quy — đặc biệt `AC-3.4` canh đúng blocker làm failover chết. Không
được tính chúng là bằng chứng "sửa này có hiệu lực".

---

## 3. Test mới thêm

| File | Số test |
|:--|:--|
| `tests/unit/core/test_rate_limit_cooldown.py` | 21 |
| `tests/unit/core/test_logger_redaction.py` | 33 |

Chạy riêng: `54 passed in 7.88s` exit 0.

⚠ **Không test nào bị sửa/xoá.** `git diff 0b2c9ba..HEAD --diff-filter=D` → **rỗng**.

---

## 4. CHƯA CHẠY (không phải PASS)

| # | Việc | Vì sao | Bằng chứng |
|:--|:--|:--|:--|
| 1 | **CI GitHub Actions** | job bị từ chối khởi động do billing; lần chạy thành công cuối **2026-10-02** | `check_all.ps1` in `CI GITHUB ACTIONS: CHUA CHAY` ở mỗi lần chạy |
| 2 | **Đo live với traffic TCBS/DNSE thật** | worktree không có `.env`; không in giá trị credential | không probe |
| 3 | **`mypy vnbroker --strict`** | **không phải gate** — `--strict` là no-op (1207 lỗi có sẵn, giống hệt `mypy vnbroker`) | `CLAUDE.md` §Gates. Gate thật là dòng 9, **PASS** |
| 4 | **`Retry-After` dạng HTTP-date** | cố ý **không** cài parser: không provider nào trong repo gửi dạng đó | `git grep -n 'X-RateLimit' 4cd0f2d` → 0 kết quả; nợ N10 |
| 5 | **DNSE market data** | TLS handshake tới `openapi.dnse.com.vn` **timeout** từ máy này | `docs/HANDOFF_TIER1_WAVE12.md` §5 B2 — **không** kết luận "DNSE hỏng" |

---

## 5. Đối chiếu số do **agent** báo với số **coordinator** đo lại

L-P05: agent tự báo là bằng chứng yếu nhất.

| Số | Agent báo | Coordinator đo lại | Kết luận |
|:--|:--|:--|:--|
| W3: 429 cố định | 3 → 1 | **3 → 1** | khớp |
| W3: AUTO 2 provider | 6 → 2 | **6 → 2** | khớp |
| W3: `should_failover` | `False` → `True` | **`False` → `True`** | khớp |
| W3: cooldown | `4.935` → `119.98` | **`119.93`** | khớp (0.05s = độ trễ snapshot) |
| T4: rò token | 4/10 → 0/10 | **4/10 → 0/10** | khớp |
| T4: bóp méo | 1/6 → 0/6 | **1/6 → 0/6** | khớp |
| `data.py` dòng | không đổi | **1823 → 1823** | khớp |
| full suite trong worktree | `1 failed, 1994 passed` | worktree thiếu `.env` ⇒ `test_dnse_integration` đỏ | **giải thích đúng**; ở main tree (có `.env`) **0 failed** |