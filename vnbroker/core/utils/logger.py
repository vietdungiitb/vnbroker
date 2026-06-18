import logging
import re
from logging.handlers import RotatingFileHandler
import os

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

# Regex pattern to match sensitive key-value pairs in various formats
SENSITIVE_PATTERN = re.compile(
    r'("|\')?(' + '|'.join(re.escape(k) for k in SENSITIVE_KEYS) + r')("|\')?\s*[:=]\s*("|\')?([^"\',\s}]+)("|\')?',
    re.IGNORECASE
)

def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive information from log messages.
    
    Args:
        text: Log message that may contain sensitive data
        
    Returns:
        String with sensitive values replaced by ***REDACTED***
    """
    if not isinstance(text, str):
        text = str(text)
    return SENSITIVE_PATTERN.sub(r'\1\2\3: "***REDACTED***"', text)

class SensitiveDataFilter(logging.Filter):
    """Logging filter to redact sensitive data from log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                redact_sensitive_data(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
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
    - log_format: str - format of the log messages. Example: '%(asctime)s - %(levelname)s - %(message)s'.
    - date_format: str - format of the timestamp in log messages. Example: '%Y-%m-%d %H:%M:%S'.
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

    # Set default log format if not provided
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
    Wrapper for advanced_logger that allows custom logging configurations.
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
