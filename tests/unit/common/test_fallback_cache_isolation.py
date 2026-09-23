import pytest
from unittest.mock import MagicMock, patch

from vnbroker.common.data import Company


@pytest.mark.unit
def test_fallback_cache_isolation_between_instances():
    """Verify that fallback cache does not leak data across different symbol instances."""
    comp_acb = Company("ACB", source="KBS")
    comp_vnm = Company("VNM", source="KBS")

    # Ensure each instance has its own separate cache dict
    assert comp_acb._fallback_cache is not comp_vnm._fallback_cache

    with patch.object(comp_acb, "_load_data_source") as mock_ds_acb, \
         patch.object(comp_vnm, "_load_data_source") as mock_ds_vnm:
        
        provider_acb = MagicMock()
        provider_acb.profile.return_value = {"symbol": "ACB"}
        mock_ds_acb.return_value = provider_acb

        provider_vnm = MagicMock()
        provider_vnm.profile.return_value = {"symbol": "VNM"}
        mock_ds_vnm.return_value = provider_vnm

        # Get fallback for ACB
        fb_acb = comp_acb._load_fallback_provider("VCI")
        assert fb_acb.profile()["symbol"] == "ACB"

        # Get fallback for VNM
        fb_vnm = comp_vnm._load_fallback_provider("VCI")
        assert fb_vnm.profile()["symbol"] == "VNM"

        # Verify key naming includes symbol
        assert "Company_ACB_VCI" in comp_acb._fallback_cache
        assert "Company_VNM_VCI" in comp_vnm._fallback_cache
        assert "Company_VCI" not in comp_acb._fallback_cache
        assert "Company_VCI" not in comp_vnm._fallback_cache
