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
    # Default logging level for all vnbroker modules
    LOG_LEVEL: int = logging.DEBUG

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
    "3.1.0": {
        "vnii": ">=0.1.5",
        
        # # Core dependencies - required for vnbroker to work
        # "requests": ">=2.25.0,<3.0.0",
        # "pandas": ">=1.3.0,<3.0.0",
        # "beautifulsoup4": ">=4.9.0,<5.0.0",
        # "packaging": ">=20.0",
        
        # # Recommended optional dependencies
        # "openpyxl": ">=3.0.0",
        # "psutil": ">=5.8.0"
    }
}

# Version-specific notices for user
VERSION_NOTICES = {
    "3.1.0": {
        "title": "vnbroker 3.1.0 - Cleanup Release",
        "release_url": "https://vnstocks.com/docs/tai-lieu/lich-su-phien-ban",
        "critical_notices": [],
        "warnings": [],
    },
}

# Python version compatibility matrix
PYTHON_VERSION_SUPPORT = {
    "3.1.0": ["3.10", "3.11", "3.12", "3.13", "3.14"]
}

