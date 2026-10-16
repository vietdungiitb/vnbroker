# HANDOVER — sua 11 defect DNSE OpenAPI + tach `trade.py` (bàn giao cho session sau)

**Trạng thái:** đã merge vào `main`, đã push, tag `v3.8.0`.
**Cổng vào duy nhất:** `pwsh -File scripts/check_all.ps1` — **exit 0** ở trạng thái này.
**Lessons áp dụng:** L-D01 · L-D02 · L-E01 · L-E02 · L-E04 · L-E06 · L-P03 · L-P05 ·
L-R01 · L-R02 · L-R03 · L-R04 · L-R06

---

## 1. NHẬT KÝ CÔNG VIỆC ĐÃ HOÀN THÀNH

### 1.1 Commit trên `feat/dnse-openapi-fix` (base `f6cf68b`, merge vào `main`)

| Commit | Nội dung |
|:--|:--|
| `0bc2d45` | Stage 0-3: AGENT_PROTOCOL, plan v2, audit độc lập, claim, probe |
| `3fbbb8b` | Slice A — D8/D9: `from`/`to` là unix **giây** + chặn `market_index` quá 2 ngày |
| `6f5fc98` | Slice B — D1: `get_working_dates` gọi `/market/working-dates` |
| `069dfbe` | Slice C — D2/D3/D4: `pageIndex` + chặn `order_history` thiếu một vế |
| `9d37af4` | Slice D — D7: `volume_profile` nhận **date string**, `board_id` bắt buộc |
| `393591e` | Slice E — D5/D6: path `corporate-action-history` + chặn `position_id` rác |
| `3e25b71` | Slice F — bằng chứng **âm** D10/D11 (hoá ra SAI — xem report §12) |
| `4746a8f` | Sửa 1 blocker + 4 major của audit mã nguồn vòng 1 |
| `51f3e30` | **Khôi phục mojibake** + thêm cổng `check_encoding.py` |
| `f0cbf68` | Type argument cho `list` trong `_list_to_frame` |
| `d8fab65` | Mang về: đóng D10/D11 bằng từ điển đo được + `pageSize` bắt buộc |
| `aff6754` | Đóng task: report final, audit 2 vòng, test report, CHANGELOG, CLAIMS |
| `73b8c99` | Lesson mới `docs/LESSONS/provider-params.md` (`L-D01`, `L-D02`) |
| `2c23984` | **#1** — `order_category` BẮT BUỘC cho `get_orders` (Owner chốt A) |
| `b4b386b` | **#2a** — đóng băng API công khai `Trade` (47 method + 14 write-gated) |
| `bdfd2cf` | **#2b** — tách `trade.py` 1352 → 4 file |

⚠ Dùng `refs/heads/main` trần khi thao tác nhánh: repo có branch `main` **và**
remote-tracking `main` → `main` trần bị **ambiguous**.

### 1.2 Ba chỉ thị Owner (sau khi task đã đóng)

| # | Việc | Commit | Ghi chú |
|:--|:--|:--|:--|
| 1 | `order_category` bắt buộc | `2c23984` | Chọn **A** (không default `NORMAL`): fail-open ngữ nghĩa dữ liệu tệ hơn `TypeError` |
| 2 | Tách `trade.py` | `b4b386b` + `bdfd2cf` | Đóng băng API **trước**, tách **sau** |
| 3 | Lesson mới, không xoá lesson cũ | `73b8c99` | Namespace 1 chữ cái: `L-D` (regex gate là `^## L-[A-Z]\d+`) |

### 1.3 Cây file sau khi tách

| File | Dòng |
|:--|:--|
| `vnbroker/connector/dnse/trade.py` (core: infra + auth + order/deal) | 622 |
| `vnbroker/connector/dnse/trade_derivatives.py` (`DerivativeMixin`) | 180 |
| `vnbroker/connector/dnse/trade_conditional.py` (`ConditionalOrderMixin`) | 180 |
| `vnbroker/connector/dnse/openapi_passthrough.py` (`OpenApiPassthroughMixin`) | 354 |

---

## 2. BẰNG CHỨNG ĐO ĐƯỢC

### 2.1 Gate cuối @ `bdfd2cf` (đã merge)

| Gate | Kết quả |
|:--|:--|
| `pytest-full` | **2281 passed, 26 skipped** (baseline 2177 ⇒ **+104**) |
| `pytest-contract` | **149 passed** (baseline 117 ⇒ +32) |
| `mypy-baseline` | PASS — 1266 → **1106** (fixed 160) |
| `encoding` | PASS — 453 file |
| `ruff-src` | PASS · `ruff-tests-all` 13 KNOWN-RED **không tăng** |

### 2.2 Đo live (không VPN)

`scripts/probe_dnse_readonly.py` ⇒ **PASS=40 FAIL=16**, cả 16 FAIL là probe phủ
định **có chủ đích**. Re-runnable — xem §4.

### 2.3 Test khoá hành vi mới

- `tests/contract/test_trade_public_surface.py` — 47 method + 47 chữ ký + 14
  write-gated. Xanh TRƯỚC (`b4b386b`) và SAU (`bdfd2cf`) khi tách.
- `tests/unit/connector/dnse/test_write_safety.py` — quét AST **cả 4 module**
  qua `TRADE_MODULES` (⚠ trước đây quét hẹp một class ⇒ bỏ sót 2 method ghi tiền).

---

## 3. ⚠️ CHƯA CHẠY — KHÔNG ĐƯỢC GHI LÀ PASS

Đây là danh sách **đầy đủ** các việc chưa đo được. Mỗi mục ghi rõ **vì sao** chưa
chạy, để phiên sau biết đâu là "chưa kịp" và đâu là "không đo được".

| # | Việc | Vì sao chưa chạy |
|:--|:--|:--|
| 1 | `STOP`/`OCO` **thật sự** hoạt động | Cần đặt lệnh thật — money lane, không được phép trong phiên này |
| 2 | `order_detail`/`executions`/`order_history` có đòi `order_category` không | Chưa probe từng endpoint; chỉ đo được `get_orders` là đòi |
| 3 | Sandbox có **chấp nhận** `pageIndex`/`pageSize` không | Chỉ biết "không đòi", chưa biết "chấp nhận" |
| 4 | `403` tại `position_id=999999` | Chưa giải thích được vì sao 403 thay vì 404 |
| 5 | `Trade.login()` JWT | `.env` thiếu `DNSE_USERNAME`/`DNSE_PASSWORD` |
| 6 | WebSocket tick stream | Chưa chạy |
| 7 | `MARKET_TYPES` so với enum server | DNSE không có file OpenAPI commit kèm sha256 (khác TCBS) |
| 8 | Mạng DNSE production | TLS handshake timeout 3/3 lần (~12.5s/lần) lúc 16:40 — **mạng lại tắt giữa phiên**, mọi kết luận live phải ghi kèm điều kiện mạng |

> Hai hằng `BOARD_IDS` / `MARKET_IDS` là tập **đã đo trên MỘT mã và MỘT ngày**,
> **không** phải enum do server công bố. Đã cố ý **không** validate cứng.

---

## 4. CÁCH CHẠY LẠI (phiên sau, theo thứ tự)

```powershell
# 0. Trạng thái
git log --oneline -5 refs/heads/main
git tag --list 'v3.8*'

# 1. Cổng gate (bắt buộc trước mọi kết luận)
pwsh -File scripts\check_all.ps1

# 2. Probe live (cần mạng DNSE, KHÔNG cần VPN)
.\.venv\Scripts\python.exe scripts\probe_dnse_readonly.py
#    -> neu TLS timeout thi ghi CHUA CHAY, KHONG suy dien PASS
```

---

## 5. NỢ TÀI LIỆU ĐÃ BIẾT (không sửa trong phiên này — cố ý)

| Nợ | Ở đâu | Vì sao để lại |
|:--|:--|:--|
| 3 heading `## [Unreleased]` cũ | `CHANGELOG.md` L596, L662, L802 | Thuộc các đợt trước; viết lại là sửa lịch sử, ngoài phạm vi merge này |
| `test_write.txt` (9 byte `"test"`) | đã **xoá** trong phiên này | Rác từ thời PAT/Gateway (đã xoá ở v3.1.0), không ai tham chiếu |
| `docs/login_tcbs.py` | `docs/` | `MANIFEST.in` ghi rõ đây là file gitignored có chủ đích + được doc TCBS tham chiếu ⇒ **giữ** |

---

## 6. GHI CHÚ VẬN HÀNH

- **CI GitHub Actions KHÔNG chạy** (job bị từ chối do billing) — mọi bằng chứng
  trong tài liệu này là **LOCAL**. Đừng ghi CI là PASS.
- `mypy vnbroker --strict` là **NO-OP**; gate thật là `scripts/check_mypy_baseline.py`.
- Tag `v3.8.0` **không** publish PyPI: `publish.yml` chỉ chạy khi tạo **GitHub
  Release** (`release: types: [published]`). Muốn publish phải tạo Release —
  đó là hành động có chủ đích của Owner.
