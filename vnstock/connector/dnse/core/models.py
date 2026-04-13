from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DNSEApiResponse:
    status: int | None
    body: dict | list | str | None
    raw: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "body": self.body,
            "raw": self.raw,
        }
