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
}

# Version-specific notices for user
VERSION_NOTICES = {
    "3.3.0": {
        "title": "vnbroker 3.3.0 - Audit Fixes Release",
        "release_url": "https://vnstocks.com/docs/tai-lieu/lich-su-phien-ban",
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
}

# Python version compatibility matrix
PYTHON_VERSION_SUPPORT = {
    "3.3.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.4.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
    "3.5.0": ["3.10", "3.11", "3.12", "3.13", "3.14"],
}

