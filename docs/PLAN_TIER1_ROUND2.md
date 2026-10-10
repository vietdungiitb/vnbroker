# PLAN v4 — Tier-1 vòng 2: P0 write gate + rò credential + chính sách failover

- **Task ID:** `TIER1-ENGINE-v2-round2`
- **Baseline:** `28db3de` (`dev`, sau khi push TIER1-ENGINE-v3)
- **Kế thừa:** `docs/PLAN_TIER1_ENGINE_v3.md` §7 (ngoài phạm vi) → nay thành in-scope
- **Planner:** Team Code Leader (supervisor)
- **Ngày:** 2026-10-08

## 0. Vì sao vòng này tồn tại

Vòng trước (`TIER1-ENGINE-v3`) đóng 5 major và đẩy 6 nhóm lỗi còn lại vào mục "ngoài phạm vi". Đây là vòng đó.

## 1. Baseline — đo bằng thực thi, không đọc tên hàm

**Đặc tả DNSE không tải được** từ máy này (`developers.dnse.com.vn` → 502/403, TLS handshake timeout; `openapi.dnse.com.vn` → timeout). ⇒ phân loại ghi/đọc **không đoán theo đặc tả**, mà suy ra từ **verb HTTP thật** mà mỗi method phát ra.

> Instrument tĩnh bị bác bỏ: quét AST tìm `requests.post(...)` trả về **0 verb** vì các method uỷ quyền qua service wrapper. Chỉ chạy thật mới đúng.

Kết quả: **47 public method · 14 có thể phát verb ghi (POST/PUT/DELETE/PATCH) · 27 read-only · 6 không chạm HTTP**.

**4 method đã có gate (`place_order`, `cancel_order`, `deposit_derivative_margin`, `withdraw_derivative_margin`) không hề phát HTTP nào** khi `enable_write()` chưa gọi ⇒ gate hoạt động, chỉ chưa áp cho 14 method kia.

### 1.1 P0 — 14 method ghi không gate, đo bằng request thật ra ngoài

`Trade(api_key='FAKE', api_secret='FAKE', base_url='https://blocked.invalid')`, **không** gọi `enable_write()`, chặn egress:

| method | verb | URL phát ra |
|---|---|---|
| `post_order` | POST | `/accounts/orders?marketType=STOCK&orderCategory=NORMAL` |
| `put_order` | PUT | `/accounts/ACC/orders/OID?marketType=STOCK` |
| `cancel_order_openapi` | DELETE | `/accounts/ACC/orders/OID?marketType=STOCK` |
| `create_trading_token` | POST | `/registration/trading-token` |
| `close_position` | POST | `/accounts/positions/POS/close?marketType=STOCK` |
| `send_email_otp` | POST | `/registration/otp` |
| `close_deal` | POST | **`https://api.dnse.com.vn`/derivative-core/deals/123/close** |
| `set_deal_pnl_config` | POST | **`https://api.dnse.com.vn`/derivative-deal-risk/pnl-configs/123** |
| `set_account_pnl_config` | PATCH | **`https://api.dnse.com.vn`/derivative-deal-risk/account-pnl-configs/ACC** |
| `place_conditional_order` | POST | — |
| `cancel_conditional_order` | PATCH | — |

⇒ **Sửa tôi trước đây sai**: đếm "9 method" (báo cáo vninvest) và "17" (AST theo tên) đều sai. Số đúng: **14 write-capable, 10 thuộc nhóm tiền thật**.

### 1.2 P0b — 3 method bỏ qua `base_url`

`close_deal`, `set_deal_pnl_config`, `set_account_pnl_config` gọi host cứng `api.dnse.com.vn` trong khi `base_url` mặc định là `openapi.dnse.com.vn`. Hai họ host khác nhau (`derivative-core`, `derivative-deal-risk`). Hệ quả: test không chặn được, không trỏ sandbox được.

> **Owner chốt (2026-10-08):** sửa để host **cấu hình được**, **giữ mặc định `api.dnse.com.vn`**. Sửa lý do: trỏ thẳng về `base_url` có thể làm hỏng lệnh derivative thật vì 2 host thuộc 2 họ API khác nhau. Đáp ứng mục tiêu (interceptable, sandbox-able) mà không đổi hành vi production. Nếu Owner muốn trỏ thẳng, đổi sau.

### 1.3 P1 — rò credential (đo bằng gọi thật)

```
Redactor.redact_url('...?api_key=AKIA123&X-Signature=deadbeef&foo=1')
  -> '...api_key=REDACTED&X-Signature=deadbeef&foo=1'     # X-Signature LỘT
Redactor.redact_headers({'Trading-Token':'SECRET','X-Api-Key':'AKIA','smart-otp':'1234','authorization':'Bearer x'})
  -> {'Trading-Token':'SECRET','X-Api-Key':'AKIA','smart-otp':'1234','authorization':'***REDACTED***'}
Redactor.redact_dict({'api-key':'SECRET','x-api-key':'AKIA','api_key':'OK'})
  -> {'api-key':'SECRET','x-api-key':'***REDACTED***','api_key':'***REDACTED***'}
```
⇒ 4 lỗ hổng: `X-Signature` trong URL, `Trading-Token`/`X-Api-Key`/`smart-otp` trong header, khoá `api-key` trong dict. Envelope dry-run (`connector/dnse/core/http_client.py`) không nhắc `X-Api-Key`.

### 1.4 P1 — hai chính sách failover khác nhau cho cùng lớp lỗi

`source_router.should_failover` trả **False** cho `OSError`, `requests.exceptions.ConnectionError`, `RuntimeError("net unreachable")` — trong khi `bulk_router.PROVIDER_ERRORS` **có** `OSError` và failover được cho cả 3. Đường single-symbol vì thế **không failover, không `record_failure`, ném thẳng ra** khi provider lỗi socket thô.

### 1.5 P1 — class `TokenBucketRateLimiter` trùng tên, cài khác hẳn

`core/utils/rate_limiter.py` (đã sửa: `capacity>=1`, `wait(max_wait=…)`) và `core/utils/async_client.py:34` định nghĩa **một class cùng tên**, chưa qua sửa, có `__aenter__`. Hai class khác nhau về hợp đồng.

### 1.6 P1 — `match_type` bị bóp méo (đo bằng gọi thật)

`process_match_types(df, 'stock', 'DNSE')` với `match_type=['F','P']` → `['ATO','unknown']`. Mã provider gốc `F` bị **ghi đè bằng phỏng đoán khung giờ**.

## 2. In-scope — 3 slice, file set rời nhau

### Slice 4 — P0 write gate (Owner đã chốt phạm vi)
| Path | Sửa |
|---|---|
| `vnbroker/connector/dnse/trade.py` | Gate **10 method tiền thật** qua `_require_write`. **KHÔNG** gate 4 method phiên/OTP (`login`, `get_trading_token`, `login_and_get_trading_session`, `send_email_otp`) — Owner chốt, để không phá luồng đăng nhập. Host derivative thành tham số cấu hình, mặc định giữ nguyên. |
| `tests/unit/connector/dnse/test_trade_write_gate.py` | MỚI — gate + host config |

### Slice 5 — P1 rò credential
| Path | Sửa |
|---|---|
| `vnbroker/broker/security/redaction.py` | `_is_sensitive_key` khớp `x-api-key`/`x-apikey`; `redact_headers` dùng chung `SENSITIVE_KEYS`; `redact_dict` dùng `_is_sensitive_key` |
| `vnbroker/connector/dnse/core/http_client.py` | Envelope dry-run mask đúng credential client thực sự gửi |
| `tests/unit/broker/test_redaction.py`, `tests/unit/connector/dnse/test_dry_run_envelope.py` | MỚI/cập nhật |

### Slice 6 — P1 chính sách chung
| Path | Sửa |
|---|---|
| `vnbroker/core/source_router.py` | `should_failover` nhận `OSError` + `requests.exceptions.*` khớp `bulk_router.PROVIDER_ERRORS` |
| `vnbroker/core/utils/async_client.py` | Bỏ class trùng tên, dùng class chuẩn đã có `max_wait` |
| `tests/contract/test_failover_policy_parity.py`, `tests/unit/core/test_rate_limiter.py` | MỚI/cập nhật |

## 3. Baseline gate @ `28db3de`

| Gate | Lệnh | Baseline |
|---|---|---|
| G1 | `pytest tests/unit tests/contract -q --timeout=300` | 🟢 0 · 1237 passed |
| G2 | `pytest tests/ -q --timeout=60` | 🟢 0 · 1308 passed |
| G3 | `ruff check vnbroker tests/unit tests/contract/` | 🟢 0 |
| G4 | `python scripts/check_mypy_baseline.py` | 🟢 0 · baseline 1266, now 1209 |
| G5 | `python scripts/check_version_sync.py` | 🟢 0 |
| G6 | `pytest tests/acceptance/test_tier1_dod.py` | 🟢 0 · 26/26 |
| G7 | probe 7 check lỗi còn treo | 🔴 **0/7** |
| G8 | GitHub Actions | ⚫ `duration_ms: 0` — **CHƯA CHẠY**, không dùng làm nghiệm thu |

## 4. AC

- **AC-4a** Với `Trade(...)` **không** gọi `enable_write()`: 10 method tiền thật **không phát HTTP nào** (đo bằng spy, không phải đọc code).
- **AC-4b** Cùng object, sau `enable_write()` + `dry_run=False`: request **có** phát ra (gate không chặn nhầm).
- **AC-4c** 4 method phiên/OTP **không** bị gate (Owner đã chốt) — có test khoá lại để không đổi nhầm về sau.
- **AC-4d** `close_deal`/`set_*_pnl_config` dùng host **cấu hình được**; mặc định vẫn `api.dnse.com.vn`; test chặn được.
- **AC-5a** `redact_url` mask `X-Signature`; `redact_headers` mask `Trading-Token`/`X-Api-Key`/`smart-otp`; `redact_dict` mask `api-key`. Giữ được case đã đúng.
- **AC-5b** Envelope dry-run **không** chứa bất kỳ credential nào client thực sự gửi.
- **AC-6a** `should_failover` và `bulk_router.PROVIDER_ERRORS` **cùng quyết định** cho: `OSError`, `requests.exceptions.ConnectionError`, `Timeout`, `HTTPError 429`, `RuntimeError` thường. Có test parity chạy trên **cả hai** policy.
- **AC-6b** Chỉ còn **một** `TokenBucketRateLimiter`; `async_client` dùng bản chuẩn và `async with` vẫn hoạt động.
- **AC-13** Mọi test mới **đỏ** trước fix (đo bằng `git show <baseline>:<path>`, **KHÔNG** `git checkout --`).
- **AC-14** G1 ≥ 1237 · G2 ≥ 1308 · G3/G4/G5/G6 exit 0 · **G7: 0/7 → 7/7**.

## 5. Non-goals

| # | Không làm | Vì sao |
|---|---|---|
| 1 | Không gate 4 method phiên/OTP | Owner đã chốt. Ghi rõ bằng test (AC-4c). |
| 2 | Không trỏ host derivative về `base_url` | 2 host khác họ API; có thể hỏng lệnh thật. Làm **cấu hình được** thay vì đổi mặc định. |
| 3 | Không sửa `match_type` (`core/utils/transform.py`) | Đổi ngữ nghĩa dữ liệu, tiêu thụ bởi `vninvest`. Cần vòng riêng với quyết định hợp đồng giá trị. Tái ticket. |
| 4 | Không sửa `vnbroker/explorer/**` | — |
| 5 | Không đổi dependency/version | — |
| 6 | Không cắt file > 800L | — |
| 7 | Không chạy `check_mypy_baseline.py --update` | Xoá gate, không phải sửa gate. |
| 8 | Không dùng GitHub Actions làm nghiệm thu | G8. |

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Gate 10 method làm hỏng người dùng đang gọi `Trade` trực tiếp | `dry_run` mặc định `True` trên các method được gate ⇒ **không** gửi lệnh thật trừ khi caller truyền `dry_run=False`; nêu rõ trong CHANGELOG là breaking |
| Đổi `should_failover` làm failover **quá** rộng, che lỗi lập trình | Chỉ thêm exception **mạng**, không đụng `KeyError`/`LookupError`/`NotImplementedError`; test phải chứng minh lỗi lập trình **vẫn** nổi lên |
| Bỏ class trùng làm hỏng `async with RATE_LIMITER` | Class chuẩn phải có `__aenter__`/`__aexit__`, hoặc thay bằng adapter giữ nguyên hợp đồng |

## 7. Điều kiện Done

- [ ] G1 ≥ 1237 · G2 ≥ 1308 · G3..G6 exit 0
- [ ] **G7: 0/7 → 7/7**
- [ ] AC-4a..6b, AC-13, AC-14 đạt
- [ ] Audit code: 0 blocker + 0 major
- [ ] Không file ngoài §2 bị sửa
- [ ] CHANGELOG ghi **breaking change** của write gate
- [ ] Merge merge-commit, push `dev`