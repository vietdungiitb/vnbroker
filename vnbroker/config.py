# vnbroker/config.py

import logging
import os

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
VERSION_REQUIREMENTS = {
    "3.3.0": {
        "vnii": ">=0.1.5",
    },
    "3.4.0": {
        "vnii": ">=0.1.5",
    },
    "3.5.0": {
        "vnii": ">=0.1.5",
    },
    "3.6.0": {
        "vnii": ">=0.1.5",
    },
}

# Version-specific notices for user
VERSION_NOTICES = {
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
}

# Python version compatibility matrix
PYTHON_VERSION_SUPPORT = {
    "3.3.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.4.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.5.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.6.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
}

