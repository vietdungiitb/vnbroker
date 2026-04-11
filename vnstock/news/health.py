"""Health snapshot helpers for News source observability."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def _sanitize_json_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Replace pandas/NumPy missing markers with JSON-safe None values."""
    sanitized: Dict[str, Any] = {}
    for key, value in record.items():
        if pd.isna(value):
            sanitized[key] = None
        else:
            sanitized[key] = value
    return sanitized


def health_snapshot_to_dataframe(
    snapshot: Dict[str, Dict[str, Any]],
    module_name: str = "news",
) -> pd.DataFrame:
    """Convert router health snapshot to a tabular frame."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for source, metrics in (snapshot or {}).items():
        row = {
            "captured_at": now_utc,
            "module": module_name,
            "source": source,
        }
        row.update(metrics or {})
        rows.append(row)

    return pd.DataFrame(rows)


def append_health_log(
    snapshot: Dict[str, Dict[str, Any]],
    file_path: str,
    fmt: str = "jsonl",
    module_name: str = "news",
) -> str:
    """Append one health snapshot to JSONL or CSV log file."""
    fmt_norm = (fmt or "jsonl").strip().lower()
    if fmt_norm not in {"jsonl", "csv"}:
        raise ValueError("fmt must be 'jsonl' or 'csv'")

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = health_snapshot_to_dataframe(snapshot, module_name=module_name)

    if fmt_norm == "csv":
        if path.exists():
            df.to_csv(path, mode="a", index=False, header=False)
        else:
            df.to_csv(path, index=False)
    else:
        records = df.to_dict(orient="records")
        with path.open("a", encoding="utf-8") as f:
            for rec in records:
                safe = _sanitize_json_record(rec)
                f.write(json.dumps(safe, ensure_ascii=False, allow_nan=False) + "\n")

    return str(path)


def sanitize_health_jsonl_file(file_path: str) -> Dict[str, int]:
    """Rewrite a JSONL file so non-standard NaN tokens become JSON null.

    Returns counters: total_lines, written_lines, skipped_lines.
    """
    path = Path(file_path)
    if not path.exists():
        return {"total_lines": 0, "written_lines": 0, "skipped_lines": 0}

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    total = 0
    written = 0
    skipped = 0

    with path.open("r", encoding="utf-8") as src, tmp_path.open("w", encoding="utf-8") as dst:
        for line in src:
            total += 1
            raw = line.strip()
            if not raw:
                skipped += 1
                continue
            try:
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    skipped += 1
                    continue
                safe = _sanitize_json_record(obj)
                dst.write(json.dumps(safe, ensure_ascii=False, allow_nan=False) + "\n")
                written += 1
            except Exception:
                skipped += 1

    tmp_path.replace(path)
    return {"total_lines": total, "written_lines": written, "skipped_lines": skipped}