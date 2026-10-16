# Provider parameters — tham số của provider đối tác

> Nhóm L-**D** (Data dictionary) sinh ra từ đợt **2026-10-16**: sửa 11 defect
> client DNSE OpenAPI. Tách riêng khởi `evidence.md` vì `evidence.md` đã **đầy**
> 120/120 dòng (trần C1) — C1 báo câo **tách tiếp**, không phải xoá lesson cũ.
> Bài học ở đây **không** nằm trong bốn nhóm cũ — nó vừa là lỗi đo lường
> (`evidence.md`) vừa là lỗi đặc tả provider (`broker-risk.md`), nhưng đứng
> riêng thì rõ hơn: **làm sao biết được tập giá trị hợp lệ của một tham số mà
> tài liệu không nói.**

---

## L-D01: Validator từ chối mà không liệt kê tập hợp — đọc response server, đừng đoán

- **Sai lầm:** 24 giá trị `boardId`/`marketId` đoán bằng trực giác
  (`HOSE`, `HNX`, `UPCOM`, `STO.G1`, `G1`, `1`…) đều bị từ chối. Từ đó suy ra
  kết luận: **"DNSE không có giá trị hợp lệ"** — rồi ghi câu đó vào docstring
  của **3 file** ("chưa tài liệu hoá").
- **Hậu quả thật:** **69 request không ra một thông tin nào**, và ba kết luận sai
  cùng lúc. Đây là **fail-open một dạng**: nó đưa ra ngoài *không có dữ liệu* và
  kết luận như thể có dữ liệu. Tệ hơn, nó **đóng băng sai** — docstring trở thành
  thứ người đọc tin, và ba lát sau sẽ viết theo đó.
- **Đúng ra (2 bước, tổng 3 request):**
  1. **Đọc chính response của server.** `GET /instruments?limit=200` trả cột
     `marketId` = `STO, HCX, UPX, STX, DVX`. Gọi lại endpoint với từng giá trị
     ⇒ cả 5 đều **200**. Tập hợp lấy được ngay, không tốn một lần đoán nào.
  2. **Bắt chước từ nơi khác trong repo.** `boardId` không có ổ nào đọc được, nhưng
     `connector/dnse/websocket.py:19,278` dùng mã `G<n>` cho kênh WS
     (`top_price.G1.json`) ⇒ thử `boardId=G1` được **200**. Quét tiếp
     `G0..G11, G20, G21` ⇒ **6** giá trị trả 200 (`G1 G2 G3 G4 G7 G8`).
- **QUY TẮC:** Trước khi viết *"không có giá trị hợp lệ"*, phải làm đủ **ba** việc:
  1. Có endpoint nào **trả về chính dữ liệu đó** không?
  2. Trong repo đã có chỗ nào **dùng mã tương tự** (WS, mobile API, tài liệu
     cũ) không?
  3. Đã đọc **đầy đủ** body lỗi chưa — validator nhiều khi **liệt kê tập giá trị
     ngay trong thông điệp lỗi**; cắt ở 90 ký tự đầu là tự bịt mình.
  Cả ba xong mà vẫn không ra ⇒ ghi **"chưa xác định"**, tuyệt đối không ghi
  "không tồn tại".
- **Tags:** `dnse` `probe` `vocabulary` `enum` `guess` `oneof` `parameters`
  `doc-drift` `fail-open` `evidence`
- **CHECKLIST:**
  - [ ] Trước khi ghi "chưa tài liệu hoá" vào docstring: đã thử đọc tập giá trị từ
        **response** của một endpoint khác chưa? (không phải đoán)
  - [ ] Đã grep toàn repo xem chỗ nào khác dùng **mã tương tự** chưa?
  - [ ] Đã log **toàn bộ** `exc.payload` (không cắt ở đầu dòng) chưa?
  - [ ] Kết luận ghi là **CHƯA CHẠY** thay vì "không tồn tại" — và câu đó có **lệnh
        tái lập** để chạy lại khi mạng về?
  - [ ] Nếu đã viết vào docstring rồi mới tìm ra ⇒ **sửa cả các file đã ghi**,
        đừng để "sự thật" sai tồn tại tiếp.
- **Proof:** `docs/REPORT_DNSE_LIVE_20261016.md` §11.4 (24 ứng viên, 0 hợp lệ)
  và §12.2 (tìm ra từ điển thật) @ `d8fab65`.
  Tái lập: `.venv\Scripts\python.exe scripts\probe_dnse_readonly.py` — mục
  `D10`/`D11`.
- **Liên hệ:** L-R04 (không kết luận "không tồn tại" khi chưa tìm) + L-P06 (không
  bịa spec). Đọc được **vẫn là để không bịa** — chỉ khác "bịa" ở chỗ "biết nguồn".

---

## L-D02: Một giá trị mặc định "cho chạy được" là tự chế — dùng giá trị đã đo

- **Sai lầm:** Khi server bắt buộc `pageSize`, tôi đặt mặc định `20` vì "hợp lý".
- **Hậu quả thật:** không có giá trị nào trong repo cho biết `20` có ý nghĩa gì —
  nó là số tôi chọn. Người đọc tưởng đó là mặc định của server. (Lần này tệ nhẹ,
  vì tham số đọc; với tham số ghi thì con số bịa đó là **tiền thật**.)
- **Đúng ra:** hoặc **đo** một giá trị rồi ghi rõ nó là giá trị đã đo
  (`page_size=20` là giá trị đo dùng được, **không phải** mặc định do server
  công bố), hoặc **bắt buộc người gọi** truyền vào.
- **QUY TẮC:** Mọi giá trị mặc định vì "cho chạy được" phải kèm nguồn: **đo** được,
  hay do **người viết chọn**? Chọn trường hợp thứ hai thì **phải nói trong
  docstring**, không được để trông như hợp đồng của server.
- **Tags:** `default` `invented` `dnse` `parameters` `doc-drift`
- **CHECKLIST:**
  - [ ] Mỗi giá trị mặc định mới có câu trả lời cho "ai quyết định số này?"
  - [ ] Docstring phân biệt được *mặc định do server công bố* với *mặc định ta chọn*?
- **Proof:** `vnbroker/connector/dnse/services/order_service.py` `get_orders`
  docstring @ `d8fab65`; đo `pageSize is required` trong
  `docs/REPORT_DNSE_LIVE_20261016.md` §12.4.