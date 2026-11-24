# vnbroker/config.py

import logging
import os
from typing import Dict

class Config:
    # -------------------------------------------------------------------------
    # HTTP request settings
    # -------------------------------------------------------------------------
    # Default timeout (in seconds) for any network request
    REQUEST_TIMEOUT: int = 30

    # Number of retry attempts on transient failures
    RETRIES: int = 3

    # Tenacity backoff strategy parameters
    BACKOFF_MULTIPLIER: float = 1.0
    BACKOFF_MIN: float = 2    # minimum wait between retries (seconds)
    BACKOFF_MAX: float = 10   # maximum wait between retries (seconds)

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    # Maximum requests per minute (0 = disabled)
    # Can be overridden via vnbroker_RATE_LIMIT_RPM environment variable
    RATE_LIMIT_RPM: int = int(os.getenv("vnbroker_RATE_LIMIT_RPM", "300"))

    # Trần cho phần cooldown do SERVER quyết định (`Retry-After`), tính bằng
    # giây. KHÔNG phải trần của phần suy đoán lũy thừa — phần đó giữ trần cũ
    # 90s để hành vi cũ không đổi. Trần riêng vì `Retry-After` là con số duy
    # nhất server chịu trách nhiệm: cắt nó ở 90s là cắt chính lời server dặn,
    # còn nâng trần của phần suy đoán lên theo giá trị này lại khiến một
    # provider trượt nhiều lần bị treo tới hàng giờ. 900s = 15 phút.
    RETRY_AFTER_MAX_SECONDS: float = float(
        os.getenv("vnbroker_RETRY_AFTER_MAX_SECONDS", "900")
    )

    # -------------------------------------------------------------------------
    # Caching
    # -------------------------------------------------------------------------
    # Max entries for LRU‑cached methods
    CACHE_SIZE: int = 128
    
    # TTL for listing cache (seconds) - default 24 hours
    # Can be overridden via vnbroker_LISTING_CACHE_TTL environment variable
    LISTING_CACHE_TTL: int = int(os.getenv("vnbroker_LISTING_CACHE_TTL", "86400"))
    
    # TTL for industry/sector mapping cache (seconds) - default 24 hours
    # Can be overridden via vnbroker_INDUSTRY_CACHE_TTL environment variable
    INDUSTRY_CACHE_TTL: int = int(os.getenv("vnbroker_INDUSTRY_CACHE_TTL", "86400"))

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    # Default logging level for all vnbroker modules (INFO to avoid spam;
    # DEBUG only when explicitly needed)
    LOG_LEVEL: int = logging.INFO

    @classmethod
    def apply_logging_config(cls):
        """
        Call once at startup to configure vnbroker logging.
        """
        logging.getLogger("vnbroker").setLevel(cls.LOG_LEVEL)


# =============================================================================
# VERSION-SPECIFIC DEPENDENCY REQUIREMENTS & NOTICES
# =============================================================================
# Define minimum required versions for each vnbroker version
# Format: "X.Y.Z": {"package_name": "min_version", ...}
#
# 2026-10-11: xoá `vnii` khỏi MỌI entry. Nó là nợ tài liệu, không phải
# dependency thật — đo bằng script, không suy đoán:
#   * `grep -ri vnii vnbroker/ tests/ scripts/` → 0 import, 0 test tham chiếu
#   * `pyproject.toml` không khai vnii ở dependencies lẫn optional-dependencies
#   * `importlib.util.find_spec('vnii')` → None (không cài trong môi trường)
#   * `_check_dependency_compatibility()` chạy thật KHÔNG hề báo vnii thiếu,
#     vì `get_version('vnii')` ném exception bị nuốt ở upgrade.py — nên entry này
#     chưa bao giờ cảnh báo được ai, chỉ là một dict vô nghĩa ai cũng đọc là thấy
#     "thư viện này cần vnii".
# Nếu sau này thật sự thêm vnii: khai vào `pyproject.toml` TRƯỚC, rồi mới thêm
# entry ở đây — và nhớ nó phải nằm trong cùng key với version đang phát hành.
# Annotation là BẮT BUỘC, không phải cho đẹp: khi mọi value đều là `{}` rỗng,
# mypy không còn value nào để suy luận kiểu nên báo `var-annotated` — đo được
# ngay sau khi xoá `vnii` (baseline 1266 -> 1139, +1 lỗi mới).
VERSION_REQUIREMENTS: Dict[str, Dict[str, str]] = {
    "3.3.0": {},
    "3.4.0": {},
    "3.5.0": {},
    "3.6.0": {},
    "3.7.0": {},
    "3.7.1": {},
    "3.7.2": {},
    "3.8.0": {},
    "3.8.1": {},
    "3.8.2": {},
    "3.9.0": {},
}

# Version-specific notices for user
VERSION_NOTICES = {
    "3.9.0": {
        "title": "vnbroker 3.9.0 - CafeF reference layer + daily_bars",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.9.0",
        "critical_notices": [
            "Them Vnbroker.reference('cafef') va daily_bars(...) cho gia lich su "
            "raw + adjusted tu CafeF (SSOT). CafeF khong vao AUTO provider pool.",
            "history(adjusted=False) cua KBS/VCI giờ tra gia tho that tu CafeF.",
            "Khong breaking change: mac dinh van tra gia dieu chinh tu provider.",
        ],
    },
    "3.8.2": {
        "title": "vnbroker 3.8.2 - fix P0 ex_date corporate actions",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.8.2",
        "critical_notices": [
            "VCI.corporate_actions() doc dung raw key `exrightDate`: ex_date va "
            "group_id 'SYMBOL:YYYY-MM-DD' Khong con None cho 100% dong nhu 3.8.1.",
            "Chi tra event (isEvent=True / co eventCode): khong con 1000 dong "
            "tin tuc lon vao contract corporate action.",
            "Khong breaking change: events() va schema 14 cot giu nguyen.",
        ],
    },
    "3.8.1": {
        "title": "vnbroker 3.8.1 - corporate action source (field so + API on dinh)",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.8.1",
        "critical_notices": [
            "VCI.corporate_actions() va facade Company.corporate_actions() tra DataFrame "
            "vo cash_amount, stock_ratio_pct, parse_status, group_id dang str 'SYMBOL:YYYY-MM-DD'. "
            "events() giu nguyen — day la them moi, khong breaking.",
            "Phat hanh cho CBCNV/ESOP co ty le %% (vd 0.5%%) duoc danh dấu unparsed, KHONG phai "
            "co phieu thuong — tranh sai factor dieu chinh gia. Chi 'Co phieu thuong' / "
            "'Tra co tuc bang Co phieu' moi set stock_ratio_pct.",
            "Hai DIV cung ex_date (vd VNM 2024-09-24) la 2 dong rieng, KHONG dedup theo title. "
            "Client tu cong theo group_id.",
        ],
    },
    "3.3.0": {
        "title": "vnbroker 3.3.0 - Audit Fixes Release",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.3.0",
        "critical_notices": [],
        "warnings": [],
    },
    "3.4.0": {
        "title": "vnbroker 3.4.0 - SSI Swap Parity Release",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.4.0",
        "critical_notices": [],
        "warnings": [],
    },
    "3.5.0": {
        "title": "vnbroker 3.5.0 - Two-Tier Architecture Release",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.5.0",
        # Breaking: quote.history() qua Vnbroker trả time tz-aware; connector/dnse
        # yêu cầu enable_write() trước khi gửi lệnh thật.
        "critical_notices": [
            "quote.history() qua Vnbroker giờ trả cột `time` dạng tz-aware "
            "(Asia/Ho_Chi_Minh) thay vì tz-naive, và được lọc theo start/end.",
            "connector/dnse: place_order/cancel_order/deposit_derivative_margin/"
            "withdraw_derivative_margin giờ cần enable_write() trước khi gửi thật.",
            "SSI không còn retry tự động trên POST đặt lệnh (chống double-submit).",
        ],
        "warnings": [
            "Đặt lệnh SSI: hãy truyền clientRequestId khi định thử lại sau lỗi mạng.",
            "Baseline mypy --strict hết hạn 2026-11-01.",
        ],
    },
    "3.7.0": {
        "title": "vnbroker 3.7.0 - Rate-limit thật + logger không rò token",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.7.0",
        # Đợt này đổi CẢ exception type người dùng thấy, CẢ số request gửi đi,
        # và CẢ cách logger redact. Ba đều là breaking.
        "critical_notices": [
            "HTTP 429 giờ ném RateLimitError thay vì ConnectionError. Đây là "
            "LỚP CON của ConnectionError nên `except ConnectionError` vẫn bắt "
            "được; nhưng `type(e) is ConnectionError` thì không còn đúng. "
            "Dùng isinstance().",
            "429 KHÔNG còn bị retry: một lệnh history() gặp 429 trước đây gửi 3 "
            "request (source cố định) hoặc 6 (AUTO, 2 provider) rồi mới xoay "
            "vòng; nay là 1 request mỗi provider rồi chuyển ngay.",
            "Cooldown của provider giờ theo `Retry-After` của server "
            "(max với suy đoán, kẹp [1, 900]s) thay vì luôn 5 * 2^(n-1).",
            "logger redact chặt hơn: `Authorization: Bearer <JWT>`, JWT trần và "
            "OTP trần nay đều bị che (trước 4/10 chuỗi thử rò). Đồng thời vá lỗi "
            "log.info('%s', dict) làm MẤT dòng log, và sửa redact quá rộng làm "
            "'monkey=abc' bị che oan.",
        ],
        "warnings": [
            "Số request tới provider GIẢM khi gặp 429. Nếu bạn dựa vào việc "
            "thử lại để che lỗi mạng, hãy bắt lỗi ở tầng trên thay vì đợi retry.",
            "CI GitHub Actions của repo này KHÔNG chạy (billing) — mọi gate chạy "
            "LOCAL qua scripts/check_all.ps1.",
        ],
    },
    "3.7.1": {
        "title": "vnbroker 3.7.1 - Chan su dung Hang 1",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.7.1",
        # Dot nay sua LOP exception nguoi dung thay (breaking) + so request
        # + cache key. Ba deu ghi bang so do o CHANGELOG Unreleased/HANG1.
        "critical_notices": [
            "HTTP 400/401/403/404/422 gio nem ProviderAuthError / "
            "ProviderNotFoundError / ProviderBadRequestError thay vi "
            "ConnectionError. Cac lop nay co y KHONG ke thua OSError de "
            "khong failover/retry. Code bat `except ConnectionError` se "
            "khong thay chung nua.",
            "Loi vinh vien la dap an cuoi: khong xoay vong provider, khong "
            "cooldown, khong retry. Pool tat ca cooling thi fail-fast thay "
            "vi quet lai.",
            "KBS/VCI loi nay nem ra thay vi tra frame rong: khong con "
            "record_success + cache 24h cho that bai.",
        ],
        "warnings": [
            "Bao transient (ca pool 500) van retry nhu cu — can Row 2.",
        ],
    },
    "3.7.2": {
        "title": "vnbroker 3.7.2 - Chan ro API secret trong log",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.7.2",
        # Ban nay dong 3 lop. Do doc bang class that (SSIListing/DNSEListing
        # giu self._api_secret) chu khong phai mo hong.
        "critical_notices": [
            "Cache HIT/MISS ghi `key#<blake2b-4>` thay vi key tho. Key tho "
            "chua gia tri attribute cua instance, trong do co credential "
            "(explorer/ssi/listing.py:58). Dung hinh dang moi: doi chieu "
            "HIT/MISS bang con so 8 ky tu.",
            "redact_sensitive_data() gio che ca khoa co tien to `_` "
            "(`_api_secret=`, `_api_key=`). Truoc do lookbehind chua `_` nen "
            "chinh field cua thu vien khong khop regex.",
            "__repr__ that bai chi con in ten exception, khong in message "
            "(message hay trich nguyen van gia tri bi loi do).",
        ],
        "warnings": [
            "Khong co breaking change: signature cua cached_listing / "
            "cached_industry / redact_sensitive_data va danh sach "
            "SENSITIVE_KEYS ghu nguyen.",
            "Ro nay co tu v3.6.0 (bo ma hoa key co kieu), khong phai do 3.7.1. "
            "3.5.0 tren PyPI khong chua no.",
        ],
    },
    "3.6.0": {
        "title": "vnbroker 3.6.0 - Tier-1 Data Contract Release",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.6.0",
        # Đợt này sửa dữ liệu SAI, nên giá trị trả về đổi — đó là breaking
        # với code đang lọc theo giá trị cũ, dù bản thân dữ liệu mới đúng.
        "critical_notices": [
            "match_type: KBS trước đây trả 'buy'/'sell'/'atc' (chữ thường) trong "
            "khi VCI trả 'Buy'/'Sell'/'ATC'. Giờ MỌI provider trả cùng một tập: "
            "Buy / Sell / ATO / ATC / unknown. Code lọc `df[df.match_type=='buy']` "
            "sẽ trả 0 dòng — hãy dùng 'Buy'.",
            "MarketSnapshot.market_cap của heatmap_data()/heatmap_df() trước đây "
            "phóng đại 1000 lần khi price_unit=None (mặc định). Ví dụ VCB: "
            "473 766 777.83 -> 473 766.78 (tỷ VND). Đơn vị giá giờ đọc từ "
            "df.attrs['price_unit'] do provider dán, thay vì suy từ tham số.",
            "Cột `time` nay luôn ở đơn vị datetime64[ns, Asia/Ho_Chi_Minh]. Trước "
            "đây KBS trả [us] và VCI trả [s]; pd.concat giữa hai frame cho "
            "dtype=object và mọi phép tính thời gian hỏng mà không ném lỗi.",
        ],
        "warnings": [
            "TCBS đã vào danh sách provider của source='AUTO' (nối cuối, sau VCI/KBS) "
            "khi có TCBS_JWT_TOKEN trong môi trường. Trước đây nó không bao giờ vào AUTO.",
            "TCBS intraday() không có thông tin mua/bán: server trả 'a' rỗng cho mọi "
            "bản ghi nên match_type là 'unknown'. Nếu cần phân tích mua/bán, hãy dùng "
            "KBS hoặc VCI.",
            "DNSE chưa được xác nhận chạy được: TLS handshake tới openapi.dnse.com.vn "
            "timeout ở máy đo 2026-10-10. Đừng mô tả là ổn định nếu chưa đo lại.",
            "Ghi đè credential cho tầng 1: file .env không được thư viện nạp tự động — "
            "hãy export biến môi trường, hoặc dùng tham số auth_token/API key.",
        ],
    },
    "3.8.0": {
        "title": "vnbroker 3.8.0 - DNSE OpenAPI: sua 11 defect + bat buoc tuong minh",
        "release_url": "https://github.com/vietdungiitb/vnbroker/releases/tag/v3.8.0",
        # Dot nay sua 11 defect client-side cua DNSE (path sai, don vi thoi gian
        # ms/giay, tham so bat buoc bi bo sot). Ba thay doi duoi day la breaking
        # THAT: code dang chay duoc se dung han, hoac te hon — chay ma SAI.
        "critical_notices": [
            "DNSE `get_orders` gio BAT BUOC truyen `order_category` "
            "('NORMAL' | 'STOP' | 'OCO'). Truoc day khong truyen thi server tra "
            "400 `INVALID_ORDER_CATEGORY`. Co y KHONG dat mac dinh 'NORMAL': "
            "nguoi muon xem STOP ma quen tham so se nhan danh sach NORMAL day du "
            "trong mat ma thieu — sai du lieu ma trong nhu dung.",
            "DNSE `get_trades_volume_profile`: `time` nhan `str` 'yyyy-MM-dd' "
            "(truoc la int, gio int -> DNSEValidationError), va `board_id` tro "
            "thanh bat buoc. Tap board do duoc: G1 G2 G3 G4 G7 G8.",
            "DNSE `get_order_history`: phai truyen CA HAI ve `from` + `to` hoac "
            "khong ve nao; mot ve -> raise thay vi tra ket qua cat cut am tham.",
        ],
        "warnings": [
            "`trade.py` 1352 dong da tach thanh 4 file (trade, trade_derivatives, "
            "trade_conditional, openapi_passthrough). API cong khai giu nguyen "
            "chu ky, khoa bang tests/contract/test_trade_public_surface.py. Neu "
            "ban import tu duong dan noi bo cu the — hay chuyen sang "
            "`vnbroker.connector.dnse.trade`.",
            "Hai hang BOARD_IDS/MARKET_IDS la tap DA DO tren mot ma va mot ngay, "
            "KHONG phai enum do server cong bo. Chua validate cung: DNSE them san "
            "moi thi gia tri ngoai tap van di ra binh thuong.",
            "Nhieu thu mucDNSE van CHUA CHAY: STOP/OCO that su hoat dong, "
            "order_detail/executions/order_history co doi order_category khong, "
            "sandbox co doi pageIndex/pageSize khong. Xem "
            "docs/HANDOFF_DNSE_FIX_20261016.md.",
            "CI GitHub Actions cua repo nay KHONG chay (billing) — moi gate chay "
            "LOCAL qua scripts/check_all.ps1.",
        ],
    },
}

# Python version compatibility matrix
PYTHON_VERSION_SUPPORT = {
    "3.3.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.4.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.5.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.6.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.7.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
}

