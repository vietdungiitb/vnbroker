# CHẨN ĐOÁN — vì sao REST production DNSE không thông (WebSocket thì có)

**Ngày:** 2026-10-09 · **Kết luận:** hỏng ở tầng TLS của **một endpoint duy nhất**,
không phải lỗi mạng, không phải lỗi code, không phải giới hạn IP.

Toàn bộ phép đo dùng `socket` + `ssl` thuần, **không** đi qua code vnbroker —
để tách bạch lỗi client khỏi lỗi hạ tầng.

---

## 1. Kết quả so sánh 4 host DNSE

| Host | IP | DNS | TCP :443 | TLS |
|---|---|---|---|---|
| **`openapi.dnse.com.vn`** | **103.151.242.24** | OK | **OK 0.4s** | **FAIL — không phản hồi** |
| `ws-openapi.dnse.com.vn` | 103.151.242.88 | OK | OK 0.5s | OK TLSv1.3 (0.9s) |
| `sb-openapi.dnse.com.vn` | 103.151.242.89 | OK | OK 0.4s | OK TLSv1.3 (0.9s) |
| `dnse.com.vn` | 103.151.242.88 | OK | OK 0.4s | OK TLSv1.3 (0.8s) |

Hai IP khác trong **cùng dải /24** (`.88`, `.89`) bắt tay TLS bình thường.
Chỉ `.24` treo.

---

## 2. TCP thành công, TLS im lặng

```
TCP connect (103.151.242.24:443)  -> OK 0.4s     ← SYN-ACK về bình thường
TLS handshake                     -> timeout 10s, 20s, 30s, và 60s
```

Máy chủ **nhận kết nối TCP nhưng không trả lời `ClientHello`**.

---

## 3. Đã loại trừ từng giả thuyết

| Giả thuyết | Cách kiểm | Kết quả |
|---|---|---|
| DNS | `getaddrinfo` | OK — chỉ **1 IP**, không có IP dự phòng |
| Chặn IP ở tầng TCP | TCP connect | **Sai** — SYN-ACK về trong 0.4s |
| Lọc theo SNI | TLS **không** đặt `server_hostname` | Vẫn timeout ⇒ không phải SNI |
| Fingerprint JA3/TLS | Gửi ClientHello **3 byte thô**, không đi qua OpenSSL | **0 byte phản hồi** ⇒ không phải fingerprint |
| Handshake quá chậm | Timeout 60s | Vẫn im lặng ⇒ loại trừ |
| Rate limit / sai key / token | — | Không thể: lỗi đó ở tầng HTTP, chưa tới được tầng TLS |
| Lỗi code vnbroker | Đo bằng `socket`+`ssl` thuần | **Loại trừ** — cùng kết quả |
| IPv6 | `getaddrinfo` trả 1 địa chỉ IPv4 | Không có đường vòng |

**Port 80 trên cả `.24` và `.88` đều timeout** ⇒ cả hai chỉ phục vụ 443, không
dùng được để phân biệt.

---

## 4. Kết luận

`openapi.dnse.com.vn` **đang không phục vụ TLS tại IP `103.151.242.24`** — nhận
kết nối rồi treo, không trả `ServerHello` dù chờ 60 giây.

Còn lại **hai khả năng**, phân biệt được bằng cách thử từ mạng khác:

1. **Sự cố phía DNSE** — máy chủ `.24` sập hoặc listener TLS treo. Nhiều khả năng hơn:
   hai endpoint cùng dải vẫn bình thường, nên không có lý do mạng nào chặn đúng
   một địa chỉ mà bỏ qua hai địa chỉ bên cạnh.
2. **Middlebox trên đường truyền của chúng ta** — có thiết bị chặn đúng đích `.24`.

> **Phép thử quyết định:** gọi `https://openapi.dnse.com.vn/accounts` từ một mạng
> khác (VPN, điện thoại 4G, máy khác).
> - Thông ⇒ vấn đề đường truyền phía chúng ta.
> - Vẫn treo ⇒ sự cố phía DNSE, cần báo DNSE.

---

## 5. Hệ quả với câu hỏi "DNSE dùng được cho Tier 1 không"

| Năng lực | Trạng thái | Bằng chứng |
|---|---|---|
| Tài khoản / số dư / lệnh | ✅ Dùng được **ngay** | Sandbox 200, test chạy thật 7/7 |
| WebSocket market data | ✅ Dùng được | 19 frame dữ liệu thật, `.88` TLS OK |
| **REST market data** | ❌ **Bị chặn bởi sự cố `.24`** | 3 phép đo TLS, không code nào liên quan |

REST market data (7 method Đợt 1) đã đúng ở mức path và `dry_run`, nhưng **chưa
từng gọi được server thật**. Không nên tính là đã kiểm chứng.

---

## 6. Việc đã làm để không lặp lại kiểu "xanh giả"

Ba nguyên nhân khiến trạng thái này bị che đậy trước đây, đã sửa ở commit `045095c`:

1. `price_depth()` nuốt lỗi và trả `DataFrame` 0 cột ⇒ lỗi mạng hiện ra như
   "hôm nay không có giao dịch".
2. `DNSEQuote`/`DNSEListing` nuốt `**kwargs` ⇒ không trỏ sandbox được ⇒ tầng
   explorer không kiểm chứng được.
3. `tests/integration/test_dnse_integration.py` không nạp `.env` ⇒ **4/4 skip
   vĩnh viễn**. Giờ: 7 pass, 0 skip.

Sau khi sửa, lỗi TLS hiện ra **ngay và đúng nghĩa** thay vì thành dữ liệu rỗng.