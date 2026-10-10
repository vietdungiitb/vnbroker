import logging
import re
from logging.handlers import RotatingFileHandler
from typing import Any
import os

REDACTED = "***REDACTED***"

# Sensitive keys that should be redacted in logs
SENSITIVE_KEYS = {
    "apiKey", "api_key", "apikey",
    "apiSecret", "api_secret", "apisecret",
    "accessToken", "access_token", "accesstoken",
    "refreshToken", "refresh_token", "refreshtoken",
    "token", "secret", "password", "passwd", "pwd",
    "username", "user", "login", "email",
    "otp", "otp_code", "otpcode", "mfa", "totp",
    "authorization", "auth", "bearer",
    "privateKey", "private_key", "privatekey",
    "secretKey", "secret_key", "secretkey",
    "clientSecret", "client_secret", "clientsecret",
    "appSecret", "app_secret", "appsecret",
    "key", "credential", "credentials",
}

# --- Rule 1: "Bearer <token>" -------------------------------------------
# WHY a separate rule: the old key:value pattern below requires a separator and
# its value class is [^"'\s,}]+ which STOPS AT WHITESPACE, so
# "Authorization: Bearer eyJ..." only ever ate the word "Bearer" and left the JWT
# sitting right there in the log file. The scheme word plus the whitespace between
# it and the credential is the whole gap, so match across it explicitly.
# Token charset = RFC 6750 b64token, so a trailing comma/quote/paren is not eaten.
#
# WHY the credential must NOT be a bare English word (audit vòng 5, finding 1):
# matching "Bearer" + any word silently destroys ordinary log prose and rewrites
# the scheme word's casing. Measured on the first version of this rule:
#   'bearer of the bond coupon' -> 'Bearer ***REDACTED*** the bond coupon'
#   'the Bearer is a role not a token' -> 'the Bearer ***REDACTED*** a role ...'
# That is precisely the L-R07 shape — a guard that destroys real data is worse
# than the leak it prevents. So the token must look like a credential: either a
# JWT (header starts with the base64 of '{"'), or long enough (>=16 chars, the
# floor of a real bearer token) to not be an English word.
BEARER_TOKEN = r'(?:eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}|[A-Za-z0-9\-._~+/]{16,}={0,2})'
BEARER_PATTERN = re.compile(
    r'(?<![A-Za-z0-9])(Bearer)([ \t]+)(' + BEARER_TOKEN + r')(?![A-Za-z0-9\-._~+/])',
    re.IGNORECASE
)

# --- Rule 2: a JWT with no key name in front of it -----------------------
# WHY: the leak that survives every key:value rule is a credential that reaches
# the log on its own ("token=%s failed" % jwt, a repr()'d payload, a raw
# response body). eyJ is base64 of the JWT header '{"', so it is a cheap and
# very low false-positive anchor.
# NOTE the trailing (?![A-Za-z0-9_-]) instead of \b: a JWT is base64url, whose
# last character may legally be '-' or '_', and \b is not a boundary there
# ("...\w" would not match before a space). \b would silently skip those.
#
# WHY the third segment may be EMPTY (audit vòng 5, finding 2): an unsigned
# "alg":"none" token legitimately ends with a bare dot, e.g.
# 'eyJhbGciOiJub25lIn0.eyJzdWIiOiIxMjM0NTY3ODkwIn0.' — requiring {6,} there let
# it through verbatim, so the "no JWT survives" guarantee did not hold.
JWT_PATTERN = re.compile(
    r'\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}(?:\.[A-Za-z0-9_-]*)?(?![A-Za-z0-9_-])'
)

# --- Rule 3: a one-time code announced without "key=value" ---------------
# WHY these words are NOT allowed to use whitespace as their separator, while
# the key:value rule below also is not: SENSITIVE_KEYS contains "user", "key",
# "auth" and "login". Making whitespace a separator turns ordinary prose into
# redaction - 'the user name is bob' becomes 'the user: "***REDACTED***" is
# bob'. A guard that destroys real data is worse than the leak it prevents
# (L-R07). So this rule is anchored on the VALUE instead: the credential must be
# 4-8 digits, and (?![\d]) keeps a longer number from being half-eaten.
# These words live here, not in SENSITIVE_KEYS, precisely so they never inherit
# the key:value separator behaviour.
OTP_PREFIXES = (
    "otp", "otp_code", "otpcode", "mfa", "totp",
    "pin", "pin_code", "pincode", "passcode",
)
OTP_PATTERN = re.compile(
    r'(?<!\w)(?:' + '|'.join(OTP_PREFIXES) + r')[\s:=]+(\d{4,8})(?![\d])',
    re.IGNORECASE
)

# --- Rule 4: key: value, with a word boundary around every key name -------
# WHY the boundary is load-bearing: "key" is a sensitive key, and without a
# boundary it matches in the MIDDLE of any word ending in "key". Measured on
# the old pattern: redact_sensitive_data('monkey=abc') returned
# 'monkey: "***REDACTED***"'. A hyphen still lets a compound name through
# ("x-api-key" keeps working because '-' is not in [A-Za-z0-9_]) while a letter
# or digit in front of the key stops the match.
# Longest alternative first: without it "secret" could win over "apiSecret"
# (case-insensitively) depending on set iteration order.
_KEY_ALTERNATIVE = '|'.join(
    sorted((re.escape(k) for k in SENSITIVE_KEYS), key=len, reverse=True)
)

SENSITIVE_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_])("|\')?(' + _KEY_ALTERNATIVE + r')(?![A-Za-z0-9_])("|\')?\s*[:=]\s*'
    r'("|\')?(?:Bearer\s+)?[^"\'\s,}]+("|\')?',
    re.IGNORECASE
)

def _redact_otp(match: "re.Match[str]") -> str:
    """Keep the label and separator, replace only the digits."""
    head = match.group(0)[:match.start(1) - match.start(0)]
    return str(head) + REDACTED


def _redact_bearer(match: "re.Match[str]") -> str:
    """Keep the scheme word and its original casing, replace only the token.

    The first version substituted a literal ``'Bearer '``, which rewrote
    ``bearer``/``BEARER`` in the log line — a cosmetic rewrite of text the user
    did not ask to change. Group 1 is the scheme as it was written, group 2 the
    whitespace after it.
    """
    return f"{match.group(1)}{match.group(2)}{REDACTED}"

def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive information from log messages.

    Rules are applied in a fixed order: Bearer -> bare JWT -> OTP -> key:value.
    The order is the contract for credentials that do NOT start with "eyJ"
    (an opaque API key behind "Bearer", a hex OTP, ...). For a real JWT the
    order happens not to matter, but it must not be randomised.

    Args:
        text: Log message that may contain sensitive data

    Returns:
        String with sensitive values replaced by ***REDACTED***
    """
    if not isinstance(text, str):
        text = str(text)
    text = BEARER_PATTERN.sub(_redact_bearer, text)
    text = JWT_PATTERN.sub(REDACTED, text)
    text = OTP_PATTERN.sub(_redact_otp, text)
    return SENSITIVE_PATTERN.sub(r'\1\2\3: "' + REDACTED + r'"', text)

def _redact_embedded(value: Any) -> Any:
    """Redact one value that is about to be formatted into a log line.

    Types are preserved on purpose. Turning everything into str() would break
    %d/%r/%f format specs and would break the arity check that %-formatting
    does on a tuple, i.e. it would lose log lines - the very class of bug this
    filter is supposed to prevent.
    """
    if isinstance(value, str):
        return redact_sensitive_data(value)
    if isinstance(value, (bytes, bytearray)):
        # surrogateescape round-trips losslessly, so bytes we do not touch come
        # back byte-for-byte; only the matched span (plain ASCII) is replaced.
        original = bytes(value)
        text = original.decode('utf-8', errors='surrogateescape')
        cleaned = redact_sensitive_data(text)
        if cleaned == text:
            return value
        return cleaned.encode('utf-8', errors='surrogateescape')
    if isinstance(value, dict):
        return {k: _redact_embedded(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(_redact_embedded(v) for v in value)
    if isinstance(value, list):
        return [_redact_embedded(v) for v in value]
    return value

def _redact_args(args: Any) -> Any:
    """Redact record.args without changing its shape.

    Python 3.13's LogRecord unwraps a single Mapping argument, so
    log.info("x=%s", {"a": 1}) stores the DICT itself in record.args, not a
    1-tuple. Iterating that "args" as if it were a tuple yields its KEYS, which
    is how the old filter turned
    log.info("x=%s", {"a": 1, "b": 2}) into
    "TypeError: not all arguments converted during string formatting" and threw
    the whole line away. So the container is handled by type, not by iteration.

    The annotations above are deliberate: `filter()` is the only typed function
    in this module, so mypy treats its body as a typed context and every call
    into an untyped helper is a NEW strict error (measured: 9 of them, all
    `no-untyped-call`/`no-untyped-def`). `Any` rather than `object` because the
    helpers return values of the type they were given, whatever that is.
    """
    if isinstance(args, (tuple, list)):
        return type(args)([_redact_embedded(a) for a in args])
    return _redact_embedded(args)

class SensitiveDataFilter(logging.Filter):
    """Logging filter to redact sensitive data from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        if hasattr(record, 'args') and record.args:
            record.args = _redact_args(record.args)
        return True

def advanced_logger(name, 
                    level='DEBUG', 
                    handler_type='stream', 
                    filename=None, 
                    log_format=None, 
                    date_format=None, 
                    max_bytes=10485760, 
                    backup_count=5):
    """
    Configure and return a customizable logger with various options.

    Parameters:
    - name: str - the logger's name. Example: 'api_logger'.
    - level: str - logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'). Example: 'INFO'.
    - handler_type: str - type of handler ('stream', 'file', 'rotating').
      'stream' will print to console, 'file' will write to a file, 'rotating' will write to a file with a max size and backup files. Example: 'rotating'.
    - filename: str - path to log file. Defaults to current directory if None provided. Example: '/var/logs/api.log'.
    - log_format: str - format for log messages. Example: '%(asctime)s - %(levelname)s - %(message)s'.
    - date_format: str - format for the timestamp in log messages. Example: '%Y-%m-%d %H:%M:%S'.
    - max_bytes: int - maximum log file size in bytes (for 'rotating' handler). Example: 10485760 (10MB).
    - backup_count: int - number of backup files to keep (for 'rotating' handler). Example: 5.

    Returns:
    - logger: logging.Logger instance.
    """
    logger = logging.getLogger(name)
    if logger.hasHandlers():  # Prevent adding multiple handlers if already configured
        logger.handlers.clear()

    # Set default file name if none provided
    if filename is None:
        filename = os.path.join(os.getcwd(), f'{name}.log')

    # Set default log format if none provided
    log_format = log_format or '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = date_format or '%Y-%m-%d %H:%M:%S'

    # Create formatter
    formatter = logging.Formatter(log_format, date_format)

    # Determine the handler type
    if handler_type == 'file':
        handler = logging.FileHandler(filename)
    elif handler_type == 'rotating':
        handler = RotatingFileHandler(filename, maxBytes=max_bytes, backupCount=backup_count)
    else:  # Default to stream handler
        handler = logging.StreamHandler()

    # Set formatter and add handler to logger
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)

    # Set the logging level
    logger.setLevel(getattr(logging, level.upper()))

    return logger

def get_logger(name, 
               level='DEBUG', 
               handler_type='stream', 
               filename=None, 
               log_format=None, 
               date_format=None, 
               max_bytes=10485760, 
               backup_count=5):
    """
    Wrapper for advanced_logger that allows custom configurations.
    Provides backward compatibility while allowing advanced customizations.

    Parameters:
    - All parameters are inherited from advanced_logger.

    Returns:
    - logger: logging.Logger instance.
    """
    return advanced_logger(name=name, 
                           level=level,
                           handler_type=handler_type,
                           filename=filename,
                           log_format=log_format,
                           date_format=date_format,
                           max_bytes=max_bytes,
                           backup_count=backup_count)