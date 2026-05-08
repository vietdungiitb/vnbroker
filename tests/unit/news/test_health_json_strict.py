import json

import pytest

from vnbroker.news.health import append_health_log


@pytest.mark.unit
class TestHealthJsonStrict:
    def test_append_health_log_serializes_nan_as_null(self, tmp_path):
        snapshot = {
            "VCI": {
                "failures": 0,
                "in_cooldown": False,
                "cooldown_remaining_sec": 0.0,
                "last_success_age_sec": float("nan"),
                "last_failure_age_sec": None,
            }
        }

        out_file = tmp_path / "strict.jsonl"
        append_health_log(snapshot, str(out_file), fmt="jsonl")

        line = out_file.read_text(encoding="utf-8").strip()
        assert "NaN" not in line

        obj = json.loads(line)
        assert obj["last_success_age_sec"] is None
