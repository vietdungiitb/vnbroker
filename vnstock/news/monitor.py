"""Monitoring helpers for News source health alerts."""

from __future__ import annotations

from typing import Any, Dict, List


def evaluate_health_alerts(
    snapshot: Dict[str, Dict[str, Any]],
    max_failures: int = 2,
    max_cooldown_sec: float = 30.0,
) -> List[Dict[str, Any]]:
    """Evaluate current snapshot and return alert records."""
    alerts: List[Dict[str, Any]] = []

    for source, metrics in (snapshot or {}).items():
        failures = int(metrics.get("failures", 0) or 0)
        in_cooldown = bool(metrics.get("in_cooldown", False))
        cooldown_remaining = float(metrics.get("cooldown_remaining_sec", 0.0) or 0.0)

        if failures >= max_failures:
            alerts.append(
                {
                    "source": source,
                    "severity": "high",
                    "type": "failure_threshold",
                    "message": f"{source} failures={failures} >= {max_failures}",
                    "metrics": metrics,
                }
            )

        if in_cooldown and cooldown_remaining >= max_cooldown_sec:
            alerts.append(
                {
                    "source": source,
                    "severity": "medium",
                    "type": "cooldown_threshold",
                    "message": (
                        f"{source} cooldown_remaining_sec={cooldown_remaining} >= {max_cooldown_sec}"
                    ),
                    "metrics": metrics,
                }
            )

    return alerts


def summarize_alerts(alerts: List[Dict[str, Any]]) -> str:
    """Build a compact text summary from alert records."""
    if not alerts:
        return "No alerts"

    parts = []
    for item in alerts:
        parts.append(f"[{item.get('severity', 'info')}] {item.get('message', '')}")
    return " | ".join(parts)
