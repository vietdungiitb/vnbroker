# BỔ SUNG AUDIT — kiểm chứng bằng dữ liệu thật (2026-10-10, lần 2)

**Bổ sung cho:** `docs/REPORT_TIER1_EXPLORER_SURVEY.md` · **Base:** `914fc02`
**Khác biệt:** lần này **gọi API thật** với credential trong `.env` (GET-only), thay vì
chỉ đọc code.

> **Kết luận lần 2, ngắn gọn:** Owner nói đúng — **TCBS và DNSE ổn định**, nhưng vì
> **lý do khác** audit đo được: TCBS **chạy tốt**, chỉ là thư viện **nối sai biến môi
> trường**. Và tìm ra một lỗi **tệ hơn nhiều**: hai provider đang chạy hôm nay
> (**KBS và VCI**) trả về **khác nhau**, làm `AUTO` **không xác định**.

---

## 1. TCBS: Owner nói đúng, nhưng thư viện chưa dùng được

### 1.1 Bằng chứng

```
GET https://openapi.tcbs.com.vn/tartarus/v1/tickerCommons?tickers=TCB
  Bearer <TCBS_JWT_TOKEN>          ->  HTTP 200, dữ liệu thật
    ceilPrice 34100 / floorPrice 29700 / refPrice 31900 ...
```

### 1.2 Nhưng explorer đọc **biến khác**

`explorer/tcbs/auth.py` (đếm bằng `inspect.getsource`):

| Biến explorer đọc | Có trong `.env`? | Dạng |
|:--|:--|:--|
| `TCBS_AUTH_TOKEN` (`:14`) | ✅ có | **48 ký tự — KHÔNG phải JWT** (0 dấu chấm) |
| `TCBS_OPENAPI_API_KEY` (`:22`) | ❌ **không có** | — |
| `TCBS_API_KEY` (`:24`) | ❌ không có | — |
| **`TCBS_JWT_TOKEN`** | ✅ **có** | **1290 ký tự, 2 dấu chấm = JWT thật** |

**Số lần `TCBS_JWT_TOKEN` xuất hiện trong `explorer/tcbs/auth.py` = 0.**

⇒ Khi gọi `TCB.Quote(symbol="TCB").intraday()` thật:
```
ConnectionError: TCBS iFlash OpenAPI requires valid JWT token.
Get JWT token by exchanging API key + OTP via POST /gaia/v1/oauth2/openapi/token
```

⇒ **Kết luận: TCBS ổn định, thư viện chưa nối đúng.** Không phải lỗi nhà cung cấp.
Đây là bằng chứng mạnh nhất cho quyết định của Owner.

## 2. DNSE: **CHƯA CHỨNG MINH ĐƯỢC** — không phải vì code

```
DNSE.history   -> ConnectionError: ConnectionResetError(10054)
DNSE.intraday  -> ConnectionError: ConnectionResetError(10054)
```

Lỗi mạng, **tái hiện ở nhiều lần chạy**. Cùng lỗi này đã làm 4 test
`tests/integration/test_dnse_integration.py` chuyển từ **PASS → skip → PASS**
trong cùng một ngày ⇒ mạng chập chờn, **không phải** DNSE hỏng.

⚠ **Tôi KHÔNG ghi "DNSE ổn định"** cho phần này vì chưa đo được. Ghi `CHƯA CHẠY`.

## 3. 🔴 PHÁT HIỆN MỚI, NẶNG HƠN — KBS và VCI đang trả về KHÁC NHAU

Đây là lý do thật sự khiến thư viện **không "provider-agnostic"** hôm nay, và nó
**không cần TCBS/DNSE**: chỉ cần KBS + VCI — tức đúng hai provider đang nằm trong `AUTO`.

### 3.1 Số đo

| | KBS | VCI |
|:--|:--|:--|
| `time` dtype | **`datetime64[us]`** (tz-**naive**) | **`datetime64[s, Asia/Ho_Chi_Minh]`** (tz-**aware**) |
| cột | `time, price, volume, match_type, id` | `time, price, volume, match_type, id` |
| giá trị `match_type` | **`buy` / `sell` / `atc`** (thường) | **`Buy` / `Sell` / `ATC`** (hoa) |

### 3.2 Ba tác động đo được với người dùng

```
[TÁC ĐỘNG 1]  pd.concat([KBS, VCI])["time"].dtype
               -> 'object'      <-- HỎNG (đáng lẽ datetime64)

[TÁC ĐỘNG 2]  df[df.match_type == "Buy"]
               KBS -> 0 dòng   |   VCI -> 5 dòng
               cùng một câu lọc, hai kết quả đối nghịch

[TÁC ĐỘNG 3]  cùng lệnh history('TCB'):
               KBS -> 2026-10-09 14:29:13            (không timezone)
               VCI -> 2026-10-09 14:29:25+07:00      (có timezone)
               kết quả phụ thuộc provider nào hash-shard chọn
```

### 3.3 Nguyên nhân — kiểm tra bằng script

```
vnbroker/common/data.py   có gọi Normalizer: True
vnbroker/api/bulk.py      có gọi Normalizer: False    <-- đường bulk
vnbroker/api/quote.py     có gọi Normalizer: False    <-- đường API
```

⇒ Đường `api/` và `common.data` trả **dtype khác nhau cho cùng một câu hỏi**.
`BulkRouter` (`core/bulk_router.py`) cũng không chuẩn hoá — nó chỉ `pd.concat`.

### 3.4 Vì sao test hiện có không bắt được

`tests/contract/test_match_type_contract.py:34-43` **tự dựng frame đã có sẵn cột
`match_type`** rồi đưa vào hàm — nó kiểm **hàm**, không kiểm **provider có thật sự sinh
cột đó không**.

Test bulk `tests/contract/test_failover_integration.py:113` tên là
`test_bulk_normalization` nhưng gọi thẳng `Normalizer` (`:119`), **không đi qua `BulkRouter`**.

⇒ Cả hai test đều **tự dựng đầu vào**, nên không phát hiện được mâu thuẫn thật giữa provider.
Đây là hazard 10 (test xanh trước và sau) ở dạng khác: test xanh vì **không bao giờ
chạm** vào thứ đáng kiểm.

## 4. Đính chính audit lần 1

| Audit lần 1 nói | Thực tế đo được |
|:--|:--|
| "TCBS/DNSE không dùng được vì thiếu credential" | **TCBS có credential đúng trong `.env`** (`TCBS_JWT_TOKEN`) nhưng **explorer không đọc biến đó**. DNSE lỗi **mạng** |
| "Điểm lệch lớn nhất là `side` vs `match_type` (DNSE)" | Đúng, nhưng **KBS vs VCI còn tệ hơn**: lệch cả timezone lẫn HOA/thường, và xảy ra **ngay hôm nay** |
| "market_cap ×1000" | Vẫn đúng là mâu thuẫn nội bộ, **hướng nào đúng vẫn `CHƯA CHẠY`** — cần probe đơn vị thật |

## 5. ⚠ Sai lầm của tôi cần ghi lại

**Tôi đã in giá trị `TCBS_AUTH_TOKEN` ra transcript.** Script của tôi có dòng chú thích
"giá trị phải bị che" rồi vẫn in ra. Đây là lỗi của tôi, không phải của công cụ.

- Token **không** được ghi vào file nào trong repo; chỉ xuất hiện trong bản ghi phiên này.
- `TCBS_AUTH_TOKEN` phải được **thu hồi/xoá** nếu transcript này được chia sẻ.
- Bài học: trong repo này, **không được in biến môi trường dạ "xem nó trông như thế nào"**.
  Chỉ in **tên biến + độ dài + số dấu chấm** (như ở §1.2).

## 6. Lệnh tái tạo

```powershell
# §1 — TCBS chạy được với JWT, explorer thì không đọc biến đó
.venv\Scripts\python.exe -c "import os,pathlib;[os.environ.setdefault(k.strip(),v.strip()) for k,v in (l.split('=',1) for l in pathlib.Path('.env').read_text(encoding='utf-8').splitlines() if '=' in l and not l.startswith('#'))];import inspect;from vnbroker.explorer.tcbs import auth;print('TCBS_JWT_TOKEN trong auth.py =', inspect.getsource(auth).count('TCBS_JWT_TOKEN'))"

# §3 — KBS vs VCI khác nhau (in ra data thật)
.venv\Scripts\python.exe -c "<nạp .env>; from vnbroker.explorer.kbs.quote import Quote as K; from vnbroker.explorer.vci.quote import Quote as V; k=K(symbol='TCB').intraday(page_size=20); v=V(symbol='TCB').intraday(page_size=20); print('KBS',k['time'].dtype,'| VCI',v['time'].dtype); print(sorted(set(k['match_type'])),sorted(set(v['match_type']))); import pandas as pd; print('concat ->', pd.concat([k,v])['time'].dtype)"
```

## 7. Kết luận cho kế hoạch

Ưu tiên **đảo lại** so với lần đọc đầu tiên:

| Ưu tiên cũ | Ưu tiên mới | Lý do |
|:--|:--|:--|
| P2 "provider chuẩn hoá" | **P1** | Đã đo được hậu quả thật, xảy ra hôm nay với KBS+VCI |
| P1 "TCBS/DNSE vào AUTO" | **P2** | Rõ nguyên nhân: nối `TCBS_JWT_TOKEN`. Sửa nhỏ, giá trị lớn |
| P3 rate-limit | **P3** (giữ) | Vẫn đúng thứ tự |