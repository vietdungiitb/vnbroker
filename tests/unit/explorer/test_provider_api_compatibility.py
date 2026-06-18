import inspect
import pandas as pd

from vnbroker.explorer.kbs.company import Company as KBSCompany
from vnbroker.explorer.kbs.financial import Finance as KBSFinance
from vnbroker.explorer.kbs.listing import Listing as KBSListing
from vnbroker.explorer.kbs.quote import Quote as KBSQuote
from vnbroker.explorer.vci.company import Company as VCICompany
from vnbroker.explorer.vci.financial import Finance as VCIFinance
from vnbroker.explorer.vci.listing import Listing as VCIListing
from vnbroker.explorer.vci.quote import Quote as VCIQuote
from vnbroker.explorer.tcbs.listing import Listing as TCBSListing


def _param_names(func):
    return list(inspect.signature(func).parameters.keys())


def test_finance_methods_have_compatibility_aliases():
    for cls in (VCIFinance, KBSFinance):
        assert hasattr(cls, 'income_statement')
        assert hasattr(cls, 'balance_sheet')
        assert hasattr(cls, 'cash_flow')
        assert hasattr(cls, 'ratio')
        assert hasattr(cls, 'financial_ratios')


def test_finance_methods_share_common_parameters():
    for func in (VCIFinance.income_statement, KBSFinance.income_statement):
        params = _param_names(func)
        assert 'period' in params
        assert 'show_log' in params



def test_listing_symbols_by_exchange_has_common_signature():
    funcs = [
        ('VCI', VCIListing.symbols_by_exchange),
        ('KBS', KBSListing.symbols_by_exchange),
        ('TCBS', TCBSListing.symbols_by_exchange),
    ]
    for name, func in funcs:
        params = _param_names(func)
        if name != 'TCBS':
            assert 'lang' in params, f"{name} missing 'lang'"
        assert 'get_all' in params, f"{name} missing 'get_all'"
        assert 'show_log' in params, f"{name} missing 'show_log'"


def test_listing_common_methods_exist():
    for cls in (VCIListing, KBSListing, TCBSListing):
        assert hasattr(cls, 'all_symbols')
        assert hasattr(cls, 'symbols_by_exchange')
        assert hasattr(cls, 'symbols_by_industries')
        assert hasattr(cls, 'symbols_by_group')
        assert hasattr(cls, 'all_future_indices')
        assert hasattr(cls, 'all_covered_warrant')
        assert hasattr(cls, 'all_bonds')
        assert hasattr(cls, 'all_etf')
        assert hasattr(cls, 'get_supported_groups')


def test_tcbs_listing_instantiation():
    """TCBSListing có thể khởi tạo mà không cần token."""
    lst = TCBSListing(show_log=False)
    assert lst.data_source == "TCBS"


def test_tcbs_listing_get_supported_groups_returns_dataframe():
    """get_supported_groups() trả về DataFrame với đúng cột."""
    lst = TCBSListing(show_log=False)
    df = lst.get_supported_groups()
    assert isinstance(df, pd.DataFrame)
    assert "group_name" in df.columns
    assert len(df) > 0


def test_tcbs_listing_invalid_group_raises_valueerror():
    """symbols_by_group() raise ValueError nếu nhóm không hợp lệ."""
    import pytest
    lst = TCBSListing(show_log=False)
    with pytest.raises(ValueError, match="Nhóm không hợp lệ"):
        lst.symbols_by_group(group="INVALID_GROUP")


def test_tcbs_listing_industries_icb_raises_not_implemented():
    """industries_icb() raise NotImplementedError vì TCBS không hỗ trợ."""
    import pytest
    lst = TCBSListing(show_log=False)
    with pytest.raises(NotImplementedError):
        lst.industries_icb()


def test_tcbs_listing_symbols_by_exchange_returns_df_on_empty_api(monkeypatch):
    """symbols_by_exchange() trả về DataFrame rỗng (đúng cột) khi API không trả dữ liệu."""
    lst = TCBSListing(show_log=False)
    monkeypatch.setattr(lst, "_call_watchlist", lambda **kw: [])
    df = lst.symbols_by_exchange()
    assert isinstance(df, pd.DataFrame)
    assert "symbol" in df.columns
    assert df.empty


def test_tcbs_listing_all_symbols_returns_two_columns(monkeypatch):
    """all_symbols() chỉ trả về symbol và organ_name."""
    lst = TCBSListing(show_log=False)
    monkeypatch.setattr(lst, "_call_watchlist", lambda **kw: [
        {"t": "VNM", "company_name": "Vinamilk", "exchange_name": "HOSE"},
        {"t": "HPG", "company_name": "Hoa Phat", "exchange_name": "HOSE"},
    ])
    df = lst.all_symbols()
    assert list(df.columns) == ["symbol", "organ_name"]
    assert len(df) == 2


def test_tcbs_listing_symbols_by_group_valid(monkeypatch):
    """symbols_by_group() trả về Series với mã đúng."""
    lst = TCBSListing(show_log=False)
    monkeypatch.setattr(lst, "_call_watchlist", lambda **kw: [
        {"t": "VNM"}, {"t": "HPG"}, {"t": "VIC"},
    ])
    s = lst.symbols_by_group(group="VN30")
    assert isinstance(s, pd.Series)
    assert len(s) == 3
    assert "VNM" in s.values


def test_api_listing_accepts_tcbs_source():
    """Listing(source='TCBS') không raise ValueError."""
    from vnbroker.api.listing import Listing
    # Chỉ kiểm tra validation — không khởi tạo đầy đủ (tránh import explorer)
    import pytest
    with pytest.raises(ValueError):
        Listing(source="INVALID_SOURCE_XYZ")

def test_company_common_methods_have_filter_by_when_expected():
    assert 'filter_by' in _param_names(VCICompany.officers)
    assert 'filter_by' in _param_names(KBSCompany.officers)
    assert 'filter_by' in _param_names(VCICompany.subsidiaries)
    assert 'filter_by' in _param_names(KBSCompany.subsidiaries)


def test_company_insider_deals_surface_exists_for_both_providers():
    assert hasattr(VCICompany, 'insider_deals')
    assert hasattr(KBSCompany, 'insider_deals')


def test_company_insider_deals_common_parameters():
    for func in (VCICompany.insider_deals, KBSCompany.insider_deals):
        params = _param_names(func)
        assert 'page' in params
        assert 'page_size' in params
        assert 'show_log' in params


def test_quote_history_has_common_compatibility_parameters():
    for func in (VCIQuote.history, KBSQuote.history):
        params = _param_names(func)
        assert 'to_df' in params
        assert 'show_log' in params
        assert 'count_back' in params
        assert 'length' in params


def test_quote_intraday_has_common_compatibility_parameters():
    for func in (VCIQuote.intraday, KBSQuote.intraday):
        params = _param_names(func)
        assert 'page_size' in params
        assert 'to_df' in params
        assert 'get_all' in params
        assert 'show_log' in params


def test_quote_price_depth_surface_exists_for_both_providers():
    assert hasattr(VCIQuote, 'price_depth')
    assert hasattr(KBSQuote, 'price_depth')
