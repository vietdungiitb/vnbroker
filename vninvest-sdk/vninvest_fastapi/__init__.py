"""
vninvest_fastapi: FastAPI integration for Vninvest SDK.

Provides a complete REST API and WebSocket server with:
- Authentication (PAT - Personal Access Tokens)
- Quota enforcement
- Usage metering
- Real-time streaming
- Admin APIs
"""

from .main import app, create_app

__version__ = "0.2.0"

__all__ = [
    "create_app",
    "app",
]
