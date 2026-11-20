"""Parse and normalize corporate actions from free-text event titles.

Background (audit 2026-11-20): VCI ``events()`` returns amounts only inside
``event_title_vi``. This module extracts numeric fields deterministically and
marks unparseable rows instead of guessing.

Rules (audit C-02, F2 chốt theo khuyến nghị):
- ``DIV + VND``  -> cash amount (Decimal).
- ``ISS + %``    -> stock ratio ONLY when title contains "Cổ phiếu thưởng" or
  "Trả cổ tức bằng Cổ phiếu". ESOP / "Phát hành cho CBCNV tỉ lệ ..." is NOT a
  bonus issue and MUST stay unparsed (it does not change the listed price).
- ``DIV + %``    -> ambiguous (cash dividend expressed as % of par value),
  never treated as a share ratio.
- VCI has no record_date/payment_date; they stay None and are never derived
  from public_date (audit C-09).
- Raw VCI rows use the key ``exrightDate`` (lower-case ``r``); rows with
  ``isEvent=False`` or no ``eventCode`` are news, not corporate actions.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import pandas as pd

CASH_RE = re.compile(r"(?P<amount>\d[\d.,]*)\s*VND", re.IGNORECASE)
PCT_RE = re.compile(r"(?P<pct>\d+(?:\.\d+)?)\s*%")
BONUS_MARKERS = ("cổ phiếu thưởng", "trả cổ tức bằng cổ phiếu")
ESOP_MARKERS = ("cbcnv", "nhân viên", "esop", "riêng lẻ")

CORPORATE_ACTION_COLUMNS = [
    "symbol",
    "action_type",
    "ex_date",
    "record_date",
    "payment_date",
    "cash_amount",
    "stock_ratio_pct",
    "currency",
    "source",
    "source_event_id",
    "raw_title",
    "parse_status",
    "group_id",
    "fetched_at",
]


@dataclass(frozen=True)
class ParsedAmount:
    cash_amount: Optional[Decimal] = None
    stock_ratio_pct: Optional[Decimal] = None
    parse_status: str = "unparsed"
    ambiguous_cash_pct: bool = False
    is_esop: bool = False


def _to_decimal(raw: str) -> Optional[Decimal]:
    """Normalize '1,500' / '2.000' / '1.500,5' to a Decimal."""
    cleaned = raw.strip()
    if "," in cleaned and "." in cleaned:
        # Last separator is the decimal separator.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        tail = cleaned.rsplit(",", 1)[-1]
        cleaned = cleaned.replace(",", "" if len(tail) == 3 else ".")
    elif "." in cleaned:
        tail = cleaned.rsplit(".", 1)[-1]
        if len(tail) == 3:
            cleaned = cleaned.replace(".", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_event_title(title: str, action_type: str) -> ParsedAmount:
    """Extract numeric amount/ratio from a Vietnamese event title.

    Args:
        title: Raw ``event_title_vi`` from VCI.
        action_type: ``DIV`` (cash dividend) or ``ISS`` (share issuance).

    Returns:
        ParsedAmount with explicit ``parse_status``; never guesses a number.
    """
    text = (title or "").lower()
    kind = (action_type or "").strip().upper()
    is_esop = any(marker in text for marker in ESOP_MARKERS)
    cash_match = CASH_RE.search(text)
    pct_match = PCT_RE.search(text)

    if kind == "DIV":
        if cash_match:
            amount = _to_decimal(cash_match.group("amount"))
            if amount is not None:
                return ParsedAmount(cash_amount=amount, parse_status="parsed_from_text")
        if pct_match:
            return ParsedAmount(ambiguous_cash_pct=True, parse_status="unparsed")
        return ParsedAmount()

    if kind == "ISS":
        if pct_match and any(marker in text for marker in BONUS_MARKERS) and not is_esop:
            ratio = _to_decimal(pct_match.group("pct"))
            if ratio is not None:
                return ParsedAmount(
                    stock_ratio_pct=ratio, parse_status="parsed_from_text", is_esop=False
                )
        return ParsedAmount(is_esop=is_esop, parse_status="unparsed")

    return ParsedAmount()


def _pick(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def _is_event_row(row: dict[str, Any]) -> bool:
    """Keep events only: the VCI endpoint mixes news into the same payload."""
    flag = _pick(row, "isEvent", "is_event")
    if isinstance(flag, str):
        if flag.strip().lower() in ("false", "0", "no", ""):
            return False
    elif flag is False:
        return False
    return bool(_pick(row, "eventCode", "event_code"))


def _date_value(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


def _normalize_date(value: Any) -> Optional[str]:
    """Convert epoch-ms int/float to ISO date; pass through ISO strings."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return pd.to_datetime(value, unit="ms").strftime("%Y-%m-%d")
    text = str(value)
    if len(text) >= 8 and text[:4].isdigit():
        return text[:10]
    return text


def normalize_events(rows: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
    """Normalize raw VCI event dicts into the contract DataFrame.

    Two events on the same ex_date are kept as two rows (audit C-05); they are
    never deduplicated by title. ``group_id`` is a JSON-serializable string.
    Rows without an event code (news) are dropped: VCI's news-events endpoint
    returns both, and the contract describes corporate actions only.
    """
    symbol = symbol.upper()
    fetched_at = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    events = [row for row in rows if _is_event_row(row)]

    for position, row in enumerate(events):
        # Real VCI key is `exrightDate` (lower-case r); `exRightDate` was wrong.
        raw_ex = _pick(row, "exrightDate", "exright_date", "exRightDate", "ex_date")
        ex_date = _normalize_date(raw_ex)
        action_type = str(_pick(row, "event_code", "eventCode") or "").upper()
        raw_title = str(_pick(row, "event_title_vi", "eventTitleVi", "event_name_vi") or "")
        parsed = parse_event_title(raw_title, action_type)

        raw_id = _pick(row, "id", "event_id", "eventId")
        if raw_id not in (None, ""):
            source_event_id = str(raw_id)
        else:
            # Positional fallback (documented): NOT stable if provider reorders.
            digest = f"{symbol}|{ex_date}|{action_type}|{position}".encode("utf-8")
            source_event_id = hashlib.sha256(digest).hexdigest()[:32]

        records.append(
            {
                "symbol": symbol,
                "action_type": action_type,
                "ex_date": ex_date,
                "record_date": None,
                "payment_date": None,
                "cash_amount": parsed.cash_amount,
                "stock_ratio_pct": parsed.stock_ratio_pct,
                "currency": "VND",
                "source": "VCI",
                "source_event_id": source_event_id,
                "raw_title": raw_title,
                "parse_status": parsed.parse_status,
                "group_id": f"{symbol}:{ex_date}",
                "fetched_at": fetched_at,
            }
        )

    return pd.DataFrame(records, columns=CORPORATE_ACTION_COLUMNS)
