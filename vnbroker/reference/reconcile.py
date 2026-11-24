"""Cross-check a provider frame against CafeF's independent adjusted series."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

DEFAULT_TOLERANCE = 0.005


@dataclass(frozen=True)
class ReconcileReport:
    ratio_mean: float
    ratio_std: float
    flagged_dates: tuple[str, ...] = field(default_factory=tuple)
    verdict: str = "adjusted_confirmed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ratio_mean": self.ratio_mean,
            "ratio_std": self.ratio_std,
            "flagged_dates": list(self.flagged_dates),
            "verdict": self.verdict,
        }


def _date_key(value: Any) -> str:
    return str(pd.Timestamp(value).strftime("%Y-%m-%d"))


def reconcile(
    provider_frame: pd.DataFrame,
    cafef_frame: pd.DataFrame,
    symbol: str = "",
    tolerance: float = DEFAULT_TOLERANCE,
) -> ReconcileReport:
    """Compare ``provider.close`` to ``cafef.close_adjusted`` without mutating inputs.

    A stable ratio confirms the provider serves adjusted prices. A ratio jump
    signals a corporate-action rebase; a ratio far below the known factor band
    signals a second adjustment applied on top of an already adjusted series.
    """
    if "close" not in provider_frame.columns or "close_adjusted" not in cafef_frame.columns:
        raise ValueError("reconcile needs provider 'close' and CafeF 'close_adjusted'")

    provider = provider_frame.copy()
    cafef = cafef_frame.copy()
    provider["_date"] = provider["time"].map(_date_key)
    cafef["_date"] = cafef["time"].map(_date_key)
    joined = provider[["_date", "close"]].merge(
        cafef[["_date", "close_adjusted"]], on="_date", how="inner"
    )
    if joined.empty:
        return ReconcileReport(0.0, 0.0, (), "no_overlap")

    ratios = [
        float(close) / float(adjusted)
        for close, adjusted in zip(joined["close"], joined["close_adjusted"])
        if adjusted
    ]
    if not ratios:
        return ReconcileReport(0.0, 0.0, (), "no_overlap")

    mean = statistics.mean(ratios)
    std = statistics.pstdev(ratios)
    flagged = tuple(
        date for date, ratio in zip(joined["_date"], ratios) if abs(ratio - mean) > tolerance
    )

    if mean < 0.2:
        verdict = "double_adjust_suspected"
    elif std > tolerance or len(flagged) > 1:
        verdict = "rebase_suspected"
    else:
        verdict = "adjusted_confirmed"

    return ReconcileReport(mean, std, flagged, verdict)
