from tests.examples.benchmark_runtime_recommendation import build_recommendation


def test_build_recommendation_prefers_kbs_when_only_kbs_is_safe():
    payload = {
        "providers": ["kbs", "vci"],
        "rows": [
            {
                "provider": "kbs",
                "concurrency": 16,
                "attempts_per_minute": 900.0,
                "success_per_minute": 900.0,
                "throttle_rate_pct": 0.0,
                "success_rate_pct": 100.0,
            },
            {
                "provider": "vci",
                "concurrency": 4,
                "attempts_per_minute": 170.0,
                "success_per_minute": 116.0,
                "throttle_rate_pct": 31.82,
                "success_rate_pct": 68.18,
            },
        ],
    }

    rec = build_recommendation(payload)

    assert rec["trading"]["primary"] == "kbs"
    assert rec["recommended_env"]["VNSTOCK_TRADING_AUTO_PRIMARY"] == "kbs"
    assert rec["recommended_env"]["VNSTOCK_KBS_ADAPTIVE_START_CONCURRENCY"] == "16"
    assert "VNSTOCK_VCI_ADAPTIVE_START_CONCURRENCY" not in rec["recommended_env"]


def test_build_recommendation_can_select_vci_when_vci_is_only_safe():
    payload = {
        "providers": ["kbs", "vci"],
        "rows": [
            {
                "provider": "kbs",
                "concurrency": 8,
                "attempts_per_minute": 200.0,
                "success_per_minute": 100.0,
                "throttle_rate_pct": 20.0,
                "success_rate_pct": 50.0,
            },
            {
                "provider": "vci",
                "concurrency": 6,
                "attempts_per_minute": 350.0,
                "success_per_minute": 340.0,
                "throttle_rate_pct": 0.0,
                "success_rate_pct": 99.5,
            },
        ],
    }

    rec = build_recommendation(payload)

    assert rec["trading"]["primary"] == "vci"
    assert rec["recommended_env"]["VNSTOCK_TRADING_AUTO_PRIMARY"] == "vci"
    assert rec["recommended_env"]["VNSTOCK_VCI_ADAPTIVE_START_CONCURRENCY"] == "6"
