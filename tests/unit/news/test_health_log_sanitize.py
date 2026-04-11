import json

import pytest

from vnstock.news.health import sanitize_health_jsonl_file


@pytest.mark.unit
class TestHealthLogSanitize:
    def test_sanitize_health_jsonl_file_rewrites_nan(self, tmp_path):
        path = tmp_path / "health.jsonl"
        path.write_text(
            "\n".join([
                '{"source":"VCI","last_success_age_sec": NaN, "last_failure_age_sec": null}',
                '{"source":"KBS","last_success_age_sec": 1.2, "last_failure_age_sec": null}',
            ])
            + "\n",
            encoding="utf-8",
        )

        stats = sanitize_health_jsonl_file(str(path))

        assert stats["total_lines"] == 2
        assert stats["written_lines"] == 2
        assert stats["skipped_lines"] == 0

        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert "NaN" not in lines[0]

        obj = json.loads(lines[0])
        assert obj["last_success_age_sec"] is None

    def test_sanitize_health_jsonl_file_missing_file(self, tmp_path):
        path = tmp_path / "missing.jsonl"
        stats = sanitize_health_jsonl_file(str(path))
        assert stats == {"total_lines": 0, "written_lines": 0, "skipped_lines": 0}
