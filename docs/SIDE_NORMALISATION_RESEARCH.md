# NGHIÊN CỨU — chuẩn hoá chiều giao dịch (`side`) đa provider

**Ngày:** 2026-10-09 · Bắt nguồn từ phát hiện: vnbroker chuẩn hoá **tên cột** `side`
nhưng **không** chuẩn hoá **giá trị** — mỗi provider trả một kiểu riêng.

Mọi khẳng định kèm `file:line`. Không đoán.

---

## 1. Kết quả khảo sát — ai trả gì

| Provider | Nguồn | Giá trị `side` | Ghi chú |
|---|---|---|---|
| **KBS** | `explorer/kbs/const.py:290` | `'B'` / `'S'` | comment ghi rõ "Trade side: 'B' (buy) or 'S' (sell)" |
| **KBS** (bản 2) | `explorer/kbs/const.py:322` | `'B'` / `'S'` | `'LC': 'side'` |
| **TCBS** (brokers) | `broker/tcbs/client.py:351` | `"BUY"` / `"SELL"` | tài liệu hàm |
| **TCBS** (derivatives) | `broker/tcbs/derivatives.py:70` | `"BUY"` / `"SELL"` | `"side": "side"` |
| **TCBS** (equity, từ API) | `broker/tcbs/equity.py:80` | `'B'` / `'S'` | `"side": "side", # B=buy, S=sell` |
| **TCBS** (equity, execType) | `broker/tcbs/equity.py:67` | `NB` / `NS` | `"execType": "side", # NB=buy, NS=sell` |
| **SSI** (stream) | `tests/unit/broker/ssi/test_stream.py:299` | `"B"` | test duy nhất khoá giá trị side |
| **DNSE** (đặt lệnh) | tài liệu `POST /accounts/{a}/orders` | `NB` / `NS` | Owner đã chốt giữ nguyên |
| **DNSE** (trades) | `explorer/dnse/quote.py:94-96` | **chưa đo được** | map danh tính, không chuyển đổi |

⇒ Ít nhất **4 kiểu giá trị** đang lẫn trong cùng một tên cột: `B/S`, `BUY/SELL`, `NB/NS`, và DNSE chưa xác định.

---

## 2. Phát hiện then chốt: **tiền lệ đã có sẵn trong repo**

### 2.1 Enum `OrderSide` tồn tại — và **hai bản trái giá trị nhau**

| Vị trí | `BUY` | `SELL` | Phạm vi |
|---|---|---|---|
| `brokerage/base.py:19-21` | `"BUY"` | `"SELL"` | tầng brokerage **dùng chung** |
| `broker/ssi/_enums.py:16-18` | `"B"` | `"S"` | **riêng SSI** |

**Không chỉ nhân đôi — chúng xung đột.** Cùng tên `OrderSide`, cùng tên thành viên
`BUY`/`SELL`, nhưng **giá trị khác nhau**.

⇒ Rủi ro tiềm ẩn thật: code import `OrderSide` từ `brokerage.base` rồi so sánh với
giá trị sinh ra từ `broker.ssi` sẽ **lệch âm thầm** — `OrderSide.BUY == "BUY"` ở
module này nhưng dữ liệu SSI là `"B"`. Không ném lỗi, chỉ cho kết quả sai.

Đây là phát hiện đáng sửa riêng, **không** gộp vào đợt port API.

### 2.2 `parse_side()` **đã** biết nhiều kiểu — và chỉ SSI dùng được

`broker/ssi/_enums.py:115-120`:
```python
def parse_side(value: str) -> OrderSide:
    """Parse side facade ("BUY"/"SELL"/"B"/"S", case-insensitive) -> OrderSide."""
    text = (value or "").strip().upper()
    if text in ("BUY", "B"):
        return OrderSide.BUY
    if text in ("SELL", "S"):
        return OrderSide.SELL
```

**Đã xử lý `B` và `BUY`.** Thiếu `NB`/`NS` — chính là kiểu DNSE dùng.

**Phạm vi:** `parse_side` chỉ được dùng **trong SSI** — 8 chỗ ở
`broker/ssi/{equity,fco,portfolio}.py` + 6 chỗ ở `tests/unit/broker/ssi/`.
Không provider nào khác gọi được ⇒ provider khác muốn dùng sẽ phải import đường dẫn
private của SSI, vi phạm ranh giới tầng.

### 2.3 TCBS đã làm đúng việc này — theo đúng kiểu Owner vừa chốt

`broker/tcbs/equity.py:364, 396`:
```python
side: 'BUY' hoặc 'SELL' (được map sang 'NB'/'NS' theo spec).
...
exec_type = "NB" if side.upper() == "BUY" else "NS"
```

**Người dùng truyền `BUY`/`SELL` → TCBS đổi thành `NB`/`NS` ở biên broker.**
Đây đúng là kiến trúc Owner chọn cho DNSE. Quyết định của Owner **nhất quán với
code sẵn có** — không phải đặt ra ngoài thiết kế.

---

## 3. Vì sao chưa ai chuẩn hoá — và vì sao điều đó **chưa** là bug nghiêm trọng

| Quan sát | Hệ quả |
|---|---|
| `common/data.py` **không có** component nào chứa trades (đọc hết: `Config`, `BaseComponent`, `StockComponents`, `EmptyProviderResult`, `Quote`, `Listing`, `Trading`, `Company`, `News`, `Finance`, `Screener`, `Fund` — `data.py:198-1852`) | DataFrame trades trả thô từ explorer, **không qua hợp đồng chung nào** ⇒ chưa có chỗ để đặt quy tắc |
| Toàn bộ repo chỉ **1 test** khoá giá trị `side` (`test_stream.py:299`) | Chuẩn hoá hầu như **không làm vỡ test** |
| Nhưng `test_ssi_live.py:111` assert **đúng** `list(df.columns) == ["time","price","volume","side"]` | Thêm cột sẽ **vỡ test này** (lộ ra ngay, không âm thầm) |

---

## 4. Ba phương án

### Phương án A — Chuẩn hoá `side` → `BUY`/`SELL` cho **mọi** provider

| | |
|---|---|
| **Cách làm** | `KBS 'B' → 'BUY'`, `TCBS 'B' → 'BUY'`, DNSE `'NB' → 'BUY'`… |
| **Ưu** | `groupby("side")` cuối cùng chạy đúng. Một giá trị duy nhất. |
| **Nhược** | **Vỡ hợp đồng âm thầm.** Code người dùng `df[df.side=="B"]` chạy hôm nay, **không báo lỗi**, chỉ ra DataFrame rỗng. Đây là loại hỏng tệ nhất. |
| **Phạm vi** | Bắt buộc sửa **cùng lúc** KBS + TCBS + SSI + DNSE — không sửa một mình DNSE. |

### Phương án B — Giữ `side` thô, **thêm cột `direction`**

| | |
|---|---|
| **Cách làm** | `side` giữ nguyên provider gửi (Lớp B). Thêm `direction = normalize_side(side)` (Lớp A). |
| **Ưu** | Không mất dữ liệu gốc. Không vỡ hợp đồng **âm thầm** — chỉ vỡ `test_ssi_live.py:111`, tức **lộ ra ngay**. Đúng cả hai nguyên tắc của Owner. |
| **Nhược** | Thêm 1 cột. Người dùng phải chuyển sang `direction` để so sánh. Hai nơi cùng nghĩa (dễ nhầm). |

### Phương án C — Không đổi gì, chỉ xuất hàm dùng khi cần

| | |
|---|---|
| **Cách làm** | `common/side.py` có `normalize_side()`; giữ nguyên DataFrame. Người dùng tự gọi. |
| **Ưu** | Zero breaking. Ít code nhất. |
| **Nhược** | `groupby("side")` **vẫn sai** — vấn đề gốc chưa giải quyết. Người dùng dễ quên gọi. |

---

## 5. Đề xuất — **B**, cộng bảng tra duy nhất

Lý do chọn B hơn A: **A hỏng âm thầm, B hỏng có tiếng.**
`df[df.side == "B"]` trả DataFrame rỗng mà không ném lỗi là thảm họa dữ liệu;
`assert list(df.columns) == [...]` đỏ lên là báo động sớm.

### 5.1 Bảng tra **một nguồn** — `vnbroker/common/side.py`

Dựa trên những giá trị **thật đang lưu hành trong repo**, không bịa thêm:

```python
# Thứ tự khớp phải thử giá trị dài hơn trước ("NB" trước "B")
_BUY_ALIASES  = {"BUY", "B", "NB", "MUA", "1"}
_SELL_ALIASES = {"SELL", "S", "NS", "BAN", "-1", "0"}   # "0" chỉ khi xác nhận provider nào dùng
```

⚠ **Bẫy phải tránh:** so khớp không theo thứ tự sẽ khớp sai — `"NB".startswith("B")`
thành `BUY` thì đúng, nhưng nếu có `"N"` (neutral) sẽ bị nuốt. Phải so **bằng set thành viên**,
không dùng `startswith`/`in` trên chuỗi con.

### 5.2 Áp dụng

| Nơi | Việc |
|---|---|
| `explorer/*/` (KBS, TCBS, SSI, DNSE, …) | thêm cột `direction` cho DataFrame trades |
| `broker/ssi/_enums.py:115` `parse_side` | **chuyển** sang `common/side.py`; giữ 1 re-export để không phá import cũ |
| `brokerage/base.py:19` `OrderSide` | giữ nguyên làm enum chuẩn |
| `broker/*/` (đặt lệnh) | **KHÔNG** đụng — giữ `NB`/`NS`/`BUY`/`SELL` bản địa (đã chốt) |

### 5.3 Cần sửa test

- `tests/integration/explorer/test_ssi_live.py:111` — thêm `"direction"` vào danh sách cột mong đợi.
- Bổ sung contract test mới khẳng định `direction` chỉ có **2** giá trị trên mọi provider.

---

## 6. Việc chưa làm được — cần Owner chốt

| Câu hỏi | Vì sao chặn |
|---|---|
| DNSE trades server gửi `side` là `NB`/`NS` hay thứ khác? | **Chưa đo được** — sandbox không có `/price/*`. Không suy từ tài liệu lệnh. |
| Có provider nào dùng `0`/`1` cho side không? | Chưa khảo sát toàn bộ. Bảng ở §5.1 cần owner xác nhận phạm vi. |
| Có `side` trả `None`/rỗng không (lệnh khớp một phần)? | Chưa đo. Phải quyết định: `direction = None` hay `UNKNOWN`. |

---

## 7. Tóm tắt

- Vấn đề **có thật**, nhưng **ít nghiêm trọng hơn vẻ ngoài**: chỉ 1 test khoá giá trị,
  và không component nào bọc trades ⇒ chưa có hợp đồng bị vi phạm.
- **Tiền lệ đã có**: TCBS đã làm đúng việc chuyển đổi ở biên broker
  (`tcbs/equity.py:396`); `parse_side()` đã xử lý `B`/`BUY`.
- **Đề xuất**: phương án B + bảng tra một nguồn ở `common/side.py`.
  Hỏng có tiếng, không hỏng âm thầm.
- **Chưa làm gì cả** — vẫn là tài liệu, chờ Owner duyệt.