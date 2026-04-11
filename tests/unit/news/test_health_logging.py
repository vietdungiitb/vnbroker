import json

import pandas as pd
import pytest

from vnstock.news.health import append_health_log, health_snapshot_to_dataframe


@pytest.mark.unit
class TestNewsHealthLogging:
    def test_health_snapshot_to_dataframe(self):
        snapshot = {
            "VCI": {
                "failures": 1,
                "in_cooldown": True,
                "cooldown_remaining_sec": 4.0,
                "last_success_age_sec": None,
                "last_failure_age_sec": 0.2,
            }
        }

        out = health_snapshot_to_dataframe(snapshot)

        assert isinstance(out, pd.DataFrame)
        assert len(out) == 1
        assert out.iloc[0]["source"] == "VCI"
        assert out.iloc[0]["module"] == "news"

    def test_append_health_log_jsonl(self, tmp_path):
        snapshot = {
            "KBS": {
                "failures": 0,
                "in_cooldown": False,
                "cooldown_remaining_sec": 0.0,
                "last_success_age_sec": 1.5,
                "last_failure_age_sec": None,
            }
        }
        out_file = tmp_path / "health.jsonl"

        result = append_health_log(snapshot, str(out_file), fmt="jsonl")

        assert result.endswith("health.jsonl")
        lines = out_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert "NaN" not in lines[0]
        payload = json.loads(lines[0])
        assert payload["source"] == "KBS"

    def test_append_health_log_csv(self, tmp_path):
        snapshot = {
            "RSS_CAFEF": {
                "failures": 2,
                "in_cooldown": True,
                "cooldown_remaining_sec": 10.0,
                "last_success_age_sec": None,
                "last_failure_age_sec": 0.1,
            }
        }
        out_file = tmp_path / "health.csv"

        append_health_log(snapshot, str(out_file), fmt="csv")

        loaded = pd.read_csv(out_file)
        assert "source" in loaded.columns
        assert loaded.iloc[0]["source"] == "RSS_CAFEF"

    def test_append_health_log_invalid_format_raises(self, tmp_path):
        with pytest.raises(ValueError):
            append_health_log({}, str(tmp_path / "health.txt"), fmt="txt")
