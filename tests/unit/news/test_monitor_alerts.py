import pytest

from vnstock.news.monitor import evaluate_health_alerts, summarize_alerts


@pytest.mark.unit
class TestNewsMonitorAlerts:
    def test_evaluate_health_alerts_thresholds(self):
        snapshot = {
            "VCI": {
                "failures": 3,
                "in_cooldown": True,
                "cooldown_remaining_sec": 40.0,
            },
            "KBS": {
                "failures": 0,
                "in_cooldown": False,
                "cooldown_remaining_sec": 0.0,
            },
        }

        alerts = evaluate_health_alerts(snapshot, max_failures=2, max_cooldown_sec=30.0)

        assert len(alerts) >= 2
        kinds = {a["type"] for a in alerts}
        assert "failure_threshold" in kinds
        assert "cooldown_threshold" in kinds

    def test_summarize_alerts(self):
        summary = summarize_alerts([
            {"severity": "high", "message": "VCI failures=3 >= 2"},
            {"severity": "medium", "message": "KBS cooldown_remaining_sec=31 >= 30"},
        ])

        assert "VCI failures=3" in summary
        assert "KBS cooldown_remaining_sec=31" in summary

    def test_summarize_alerts_empty(self):
        assert summarize_alerts([]) == "No alerts"
