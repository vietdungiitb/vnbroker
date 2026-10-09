# SUMMARY — a2-ws: viết lại tầng WebSocket TCBS theo protocol chính thức

**Worktree:** `C:\Mujoco Projects\tcbs-a2-ws` · **Branch:** `feat/a2-ws`
**Base:** `dev @ bec8b82` · **Ngày:** 2026-10-09
**Slice:** a2 (PLAN_TCBS_REBUILD.md §3 S2, 9 AC)

---

## 1. Commit

```
f2ba384  feat(tcbs-ws): viết lại tầng WebSocket theo protocol thesis chính thức
```

4 files changed, 1711 insertions(+), 399 deletions(-).
Không có `--no-verify`. Pre-commit hook chạy bình thường (exit 0).

---

## 2. File đã đổi

| File | Trước | Sau | Nội dung |
|---|---|---|---|
| `vnbroker/explorer/tcbs/websocket.py` | 412L | **791L** | Viết lại toàn bộ theo protocol `thesis` |
| `vnbroker/explorer/tcbs/ws_models.py` | 89L | **276L** | Thêm model protocol + coercion + converter |
| `vnbroker/explorer/tcbs/stream.py` | 170L | **246L** | Facade typed, giữ chữ ký cũ |
| `tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py` | — | **670L** (mới) | 60 test offline |

`websocket.py` 791L — **dưới trần 800L** (`CLAUDE.md:15`). Không vượt.

Không sửa file nào ngoài danh sách cho phép.

---

## 3. Sáu lỗi protocol đã sửa

Bảng "kẻ thẻ này để đối chiếu" — mỗi dòng là code cũ vs tài liệu chính thức:

| # | Protocol chính thức | Code cũ |
|---|---|---|
| 1 | TEXT frame phân tách bằng `\|` | `json.dumps({"cmd":"subscribe",...})` |
| 2 | Auth = frame `d\|a\|\|\|base64(token)` | header HTTP `Authorization: Bearer` |
| 3 | Chờ `d\|0\|{"success":true}` rồi mới subscribe | `connect()` trả về ngay |
| 4 | Heartbeat `d\|p\|\|\|` mỗi 2s, đọc `d\|33\|15` | `{"cmd":"ping"}` / `{"cmd":"pong"}` |
| 5 | `ping_interval=None, ping_timeout=None` (tắt auto-ping) | `ping_interval=None` nhưng `ping_timeout` để mặc định |
| 6 | `normal` và `derivative` channel ID rời nhau | một `_parse_channel_data` dùng chung |

Endpoint đúng lại (tài liệu 5.2 và 7.2):

```
wss://openapi.tcbs.com.vn/ws/thesis/v1/stream/normal
wss://openapi.tcbs.com.vn/ws/thesis/v1/stream/derivative
```

Code cũ trỏ `ouranos` / `aither` / `nesoi` — 3 endpoint **không có trong tài liệu
v1.0.0** (AC audit đã ghi chúng là "chưa đúng"). `StreamType.OURANOS`,
`AITHER`, `NESOI` giữ làm alias enum của `NORMAL`/`DERIVATIVE` để AC9 không
vỡ.

---

## 4. Mapping channel (đọc từ tài liệu, không suy đoán)

**`/stream/normal`** — `STOCK_CHANNEL_IDS` (`websocket.py:127`)

| code | id | tên | kiểu |
|---|---|---|---|
| `bi` | `s\|1` | bid | giá/KL **string** |
| `op` | `s\|2` | offer | giá/KL **string** |
| `fe` | `s\|3` | foreign | **string** |
| `bp` | `s\|4` | base_price | **number** |
| `mp` | `s\|5` | session | **number** |
| `tm` | `s\|6` | ticker_match | giá/KL **string**, change number |
| `rt` | `s\|8` | stock_index | **number** |
| `pta` | `s\|16` | pt_advertisement | number |
| `ptm` | `s\|17` | pt_match | number |
| `tmh` | `s\|22` | ticker_match_history | giá/KL string |

**`/stream/derivative`** — `DERIVATIVE_CHANNEL_IDS` (`websocket.py:143`)

| code | id | tên | kiểu |
|---|---|---|---|
| `tm` | `s\|21` | ticker_match | **number** |
| `bi` | `s\|23` | bid | **number** |
| `op` | `s\|24` | offer | **number** |
| `mp` | `s\|27` | day_summary | **number** |

Hai bảng rời nhau (`isdisjoint`) — test `test_ac6_channel_registries_are_separate_objects`.
Hai hàm parse riêng, không gọi chung — test `test_ac6_parser_functions_are_not_shared`
khẳng định `parse_normal_frame is not parse_derivative_frame`.

---

## 5. Gate — output thật

Tất cả chạy trong worktree `tcbs-a2-ws`. **Worktree không có file `.env`**
(`Test-Path .env` → `False`) nên baseline phải tự đo, không ép khớp main tree.

### 5.1 Baseline worktree (đo trước khi sửa, lúc `bec8b82`)

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
```

```
1 failed, 1492 passed, 30 skipped, 2 warnings in 149.98s
FAILED tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible
  AssertionError: khong thay DNSE_API_SECRET trong moi truong
```

```powershell
.venv\Scripts\python.exe -m ruff check vnbroker          # All checks passed!   exit 0
.venv\Scripts\python.exe scripts/check_mypy_baseline.py   # no new strict errors (baseline 1266, now 1207, fixed 59)  exit 0
```

### 5.2 Sau thay đổi

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
```

```
1 failed, 1552 passed, 30 skipped, 2 warnings in 127.86s (sau commit)
FAILED tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible
```

**Delta: +60 passed** (1492 → 1552). Test fail **giống hệt baseline**, không
liên quan TCBS:

```powershell
Test-Path .env          # False  — .env bị gitignore, worktree không có
$env:DNSE_API_SECRET    # rỗng
```

Test đó kiểm tra `DNSE_API_SECRET` có trong môi trường. Worktree không có
`.env` nên không có biến đó. Xác nhận độc lập:

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_dnse_integration.py::TestEnvVisibility -q
# 1 failed, 2 passed — chỉ test env visibility fail
```

```powershell
.venv\Scripts\python.exe -m ruff check vnbroker
# All checks passed!    exit 0

.venv\Scripts\python.exe scripts/check_mypy_baseline.py
# OK: no new strict errors (baseline 1266, now 1207, fixed 59).
# exit 0
```

Trong lúc code còn 5 lỗi mypy mới (`type-arg` trên `Queue`/`Task`, `arg-type`
trên 2 hàm converter) — đã sửa bằng `asyncio.Queue[Any]`,
`asyncio.Task[None]`, và `Optional[StreamMessage]`. Baseline giữ nguyên 1266/1207.

### 5.3 Gate phụ

```powershell
.venv\Scripts\python.exe -m ruff check tests
# Found 13 errors.   exit 1
```

**ĐỎ SẴN, không phải do lát này.** Đếm lại ở `bec8b82` cũng 13 lỗi; plan §0
ghi rõ "13 lỗi KNOWN-RED có sẵn — không được đòi PASS". File test mới của lát
này sạch:

```powershell
.venv\Scripts\python.exe -m ruff check tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py
# All checks passed!   exit 0
```

### 5.4 Gate CHƯA CHẠY

| Gate | Lý do |
|---|---|
| Kết nối server TCBS thật, xác nhận auth/subscribe/heartbeat | Không có token OpenAPI hợp lệ trong môi trường. Plan §3b R3 đã ghi rủi ro này: `apikey/info` trả 200 nhưng cần Smart OTP để đổi ra JWT. |
| Đo round-trip thật của `s\|1` … `s\|22` | Cùng lý do trên. Mọi frame trong test lấy từ **tài liệu**, không phải từ capture server. |
| `ruff check tests` xanh | Gate này đỏ sẵn ở base, nằm ngoài phạm vi lát. |
| Kiểm chứng `openapisit.tcbs.com.vn` DNS FAIL lại | Đã đo ở lát trước, không cần đo lại. Kết quả được tin theo audit đã commit. |

---

## 6. FAIL trước / PASS sau

Bằng chứng cho test mới, dùng đúng thứ tự quy định:

1. Copy 3 file nguồn ra `%TEMP%\a2ws-backup\`.
2. `git show HEAD:<file> > <file>` — **không** dùng `git checkout --`.
3. Chạy test với code cũ.
4. Copy lại bản mới, chạy lại.

**Code cũ (`bec8b82`):**

```
collected 0 items / 1 error
ERROR tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py
ImportError: cannot import name 'trade_from_message'
1 error in 7.70s     exit 2
```

**Code mới (`f2ba384`):**

```
60 passed in 5.59s     exit 0
```

Ngoài ra 4 test fail trong lúc code mới còn lỗi (`build_order_book` so sánh
channel sai, `is_connected` assert sau `disconnect`, regex SIT quá rộng) — đã
sửa và xanh.

---

## 7. AC → test

| AC | Test | Kết quả |
|---|---|---|
| 1 auth là frame, không phải header | `test_ac1_auth_token_is_base64_encoded`, `test_ac1_auth_frame_shape_is_pipe_delimited`, `test_ac1_connect_sends_auth_frame_and_no_authorization_header` | PASS |
| 2 chờ `d\|0\|success` | `test_ac2_auth_failure_raises_and_never_subscribes`, `test_ac2_subscribe_before_auth_is_rejected`, `test_ac2_client_waits_for_auth_ack_before_returning_connect` | PASS |
| 3 subscribe / unsubscribe | `test_ac3_subscribe_frame_matches_doc_example`, `test_ac3_unsubscribe_frame_matches_doc_example`, `test_ac3_client_sends_pipe_frames_over_the_socket`, `test_ac3_snapshot_request_frame_matches_doc_example` | PASS |
| 4 heartbeat | `test_ac4_heartbeat_frame_shape`, `test_ac4_heartbeat_task_emits_text_frame`, `test_ac4_server_timeout_frame_is_understood`, `test_ac4_timeout_frame_updates_client_state` | PASS |
| 5 parse `s\|<CH>\|<JSON>`, giữ raw | `test_ac5_data_frame_splits_on_pipe_and_keeps_raw_text`, `test_ac5_stock_prices_and_volumes_stay_strings`, `test_ac5_every_documented_stock_frame_parses` | PASS |
| 6 channel riêng 2 endpoint | `test_ac6_stock_channel_ids_are_unknown_on_derivative`, `test_ac6_derivative_channel_ids_are_unknown_on_stock`, `test_ac6_channel_registries_are_separate_objects`, `test_ac6_parser_functions_are_not_shared` | PASS |
| 7 xoá SIT | `test_ac7_sit_endpoint_table_is_gone`, `test_ac7_no_sit_host_anywhere_in_module_source`, `test_ac7_production_urls_are_the_documented_ones` | PASS |
| 8 offline | toàn bộ module dùng frame hằng + `FakeSocket` monkeypatch `websockets.connect`; `test_offline_end_to_end_pump`, `test_offline_derivative_pump` | PASS |
| 9 tương thích `stream.py` | `test_ac9_legacy_stream_type_names_still_resolve`, `test_ac9_subscribe_signature_unchanged`, `test_ac9_use_sit_flag_is_still_accepted`, `test_ac9_legacy_channel_names_are_accepted`, `test_ac9_legacy_channel_name_subscribe_still_sends_tcbs_codes`, `test_ac9_ws_models_legacy_dataclasses_are_intact` | PASS |

Ngoài AC: 1 test bảo vệ `ping_interval`/`ping_timeout` đều `None` —
`test_ac_auto_ping_is_disabled_on_connect`. Đây là nguyên nhân #1 gây
disconnect 1002 theo FAQ tài liệu, không test thì dễ tái phát.

---

## 8. Rủi ro

| # | Rủi ro | Mức | Bằng chứng | Giảm thiểu |
|---|---|---|---|---|
| R1 | **Chưa probe server thật.** Mọi frame lấy từ tài liệu, không phải capture. Nếu server gửi thêm field hoặc channel ID khác, parser drop frame kèm warning. | Cao | Không có token (`R3` của plan) | Mọi frame parse đều giữ `msg.raw`; `test_ac5_every_documented_stock_frame_parses` liệt kê đủ frame tài liệu để thêm frame mới chỉ cần 1 dòng |
| R2 | `stream_ohlc` và `stream_matching` nay ném `NotImplementedError`. Gọi cũ âm thầm trả rỗng; giờ ném lỗi rõ. Đây là **thay đổi hành vi**, không phải bug. | Trung bình | Protocol không có kênh OHLC/khớp lệnh; tài liệu v1.0.0 xác nhận | Ném `NotImplementedError` kèm hướng dẫn thay thế, thay vì trả về im lặng |
| R3 | `StreamType.OURANOS/AITHER/NESOI` nay trỏ sang endpoint thesis, tức đổi endpoint thật so với tên gọi cũ. Code cũ trỏ endpoint không có trong tài liệu ⇒ nhiều khả năng cũng không hoạt động. | Trung bình | Audit: 3 endpoint đó "chưa đúng", chỉ 2 stream `thesis` là bảng giá | Alias giữ để không phá import; docstring ghi rõ là alias deprecated |
| R4 | `use_sit=True` nay chỉ ghi warning, im lặng bỏ qua. Nếu có môi trường SIT thật trong tương lai, code sẽ nối production. | Thấp | `openapisit.tcbs.com.vn` DNS FAIL (đã đo) | Warning ở constructor; `test_ac7_no_sit_host_anywhere_in_module_source` chặn URL `wss://…sit` quay lại |
| R5 | Reconnect path `_reconnect()` **chưa** có test — cần server thật để kích hoạt. | Thấp | Không có token | Đánh dấu `# pragma: no cover`; logic backoff theo tài liệu (`min(2^n, 30)`, tối đa 10) |
| R6 | `websocket.py` 791L, cách trần 800L chỉ 9 dòng. Thêm logic sẽ vượt. | Thấp | Đếm bằng `(Get-Content -Encoding utf8 <file>).Count` | Tách phần typed converter sang `ws_models.py` (đã làm một phần) nếu cần mở rộng |

---

## 9. Bài học

1. **Đọc tài liệu trước khi tin code đang chạy.** `websocket.py` cũ trông
   hoàn chỉnh 412L nhưng sai cả 6 điểm protocol. Không có test nào chạm
   tới (grep `TCBSWebSocketClient` trong `tests/` → 0 kết quả), nên nó hỏng
   im lặng suốt thời gian qua. Đây chính là hazard P4 trong plan.
2. **Một test module mới làm lộ lỗi thiết kế, không chỉ lỗi cú pháp.** Test
   `test_ac6_parser_functions_are_not_shared` buộc phải tách hai hàm parse.
   Nếu viết test sau khi code, dễ bỏ qua điều này.
3. **Baseline phải tự đo, không ép khớp.** Worktree không có `.env` nên
   baseline ở đây là `1 failed, 1492 passed`, khác `1497 passed` của main
   tree trong plan. Ép khớp sẽ tạo ra một "failure giả" hoặc một pass giả.
4. **`git show HEAD:<file> > <file>` hoạt động, `git checkout --` thì không.**
   Copy ra `%TEMP%` trước rồi restore bằng `git show` đã chứng minh được ở
   §6.
5. **Ví dụ trong tài liệu là dữ liệu test tốt nhất.** 14 frame trong test lấy
   nguyên văn từ docs (kể cả token thật trong ví dụ của TCBS), nên test có
   giá trị kiểm chứng thay vì chỉ khớp cấu trúc tự thỏa.
6. **Gate đỏ sẵn phải đo trước khi sửa.** `ruff check tests` đỏ 13 lỗi ở
   base; nếu đo sau khi sửa mới thì không biết 13 là của mình hay có sẵn.

---

## 10. Lệnh tái lập toàn bộ số liệu

```powershell
cd "C:\Mujoco Projects\tcbs-a2-ws"

# baseline (đo trên HEAD hiện tại = code đã sửa)
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
# → 1 failed, 1552 passed, 30 skipped

# baseline pre-change (đo lại từ bec8b82)
git stash list
$tmp = "$env:TEMP\a2ws-baseline"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
foreach ($f in @("vnbroker/explorer/tcbs/websocket.py",
                 "vnbroker/explorer/tcbs/ws_models.py",
                 "vnbroker/explorer/tcbs/stream.py")) {
  Copy-Item $f (Join-Path $tmp ($f -replace '/','__')) -Force
  git show "bec8b82:$f" | Out-File -Encoding utf8 $f
}
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
# → 1 failed, 1492 passed, 30 skipped   (delta +60)

# FAIL trước / PASS sau
git show "bec8b82:vnbroker/explorer/tcbs/ws_models.py" | Out-File -Encoding utf8 vnbroker\explorer\tcbs\ws_models.py
.venv\Scripts\python.exe -m pytest tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py -q -p no:cacheprovider
# → 1 error (ImportError), exit 2
git show "f2ba384:vnbroker/explorer/tcbs/ws_models.py" | Out-File -Encoding utf8 vnbroker\explorer\tcbs\ws_models.py
.venv\Scripts\python.exe -m pytest tests/unit/explorer/tcbs/test_tcbs_ws_protocol.py -q -p no:cacheprovider
# → 60 passed

# gate còn lại
.venv\Scripts\python.exe -m ruff check vnbroker            # exit 0
.venv\Scripts\python.exe -m ruff check tests               # exit 1 — 13 lỗi KNOWN-RED, có sẵn
.venv\Scripts\python.exe scripts/check_mypy_baseline.py    # exit 0

# ngân sách dòng
(Get-Content -Encoding utf8 vnbroker\explorer\tcbs\websocket.py).Count   # 791
(Get-Content -Encoding utf8 vnbroker\explorer\tcbs\ws_models.py).Count   # 276
(Get-Content -Encoding utf8 vnbroker\explorer\tcbs\stream.py).Count      # 246
```

> Lưu ý: `Out-File -Encoding utf8` trên PowerShell 7 ghi BOM-free UTF-8 và
> thêm newline cuối. Khi restore bằng `git show`, hãy kiểm tra
> `git diff --stat` trước khi commit — dùng đúng thứ tự copy/restore như §6.

---

## 11. Việc chưa làm (ngoài phạm vi lát a2)

- Probe server thật khi có token — sẽ xác nhận hoặc bác bỏ giả định trong §4.
- Viết test cho `_reconnect()` — cần server thật.
- Cân nhắc tách typed converter khỏi `websocket.py` nếu file vượt 800L.
- GĐ4 TokenManager, GĐ5 13 endpoint còn lại — lát sau theo plan.