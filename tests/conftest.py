"""Pytest configuration with automatic .env loading."""
import os
from pathlib import Path

# Load .env file before any tests run
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, skip

# Ensure test environment
os.environ.setdefault("PYTEST_RUNNING", "1")

# Load fixtures and enhancements plugins
pytest_plugins = [
    "tests.fixtures",
    "tests.conftest_enhancements",
]