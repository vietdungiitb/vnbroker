import inspect

from vnbroker.explorer.kbs.company import Company as KBSCompany
from vnbroker.explorer.kbs.financial import Finance as KBSFinance
from vnbroker.explorer.kbs.listing import Listing as KBSListing
from vnbroker.explorer.kbs.quote import Quote as KBSQuote
from vnbroker.explorer.vci.company import Company as VCICompany
from vnbroker.explorer.vci.financial import Finance as VCIFinance
from vnbroker.explorer.vci.listing import Listing as VCIListing
from vnbroker.explorer.vci.quote import Quote as VCIQuote


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
    for func in (VCIListing.symbols_by_exchange, KBSListing.symbols_by_exchange):
        params = _param_names(func)
        assert 'lang' in params
        assert 'get_all' in params
        assert 'show_log' in params


def test_listing_common_methods_exist():
    for cls in (VCIListing, KBSListing):
        assert hasattr(cls, 'all_symbols')
        assert hasattr(cls, 'symbols_by_industries')
        assert hasattr(cls, 'symbols_by_group')
        assert hasattr(cls, 'all_future_indices')
        assert hasattr(cls, 'all_covered_warrant')
        assert hasattr(cls, 'all_bonds')
        assert hasattr(cls, 'all_etf')
        assert hasattr(cls, 'get_supported_groups')


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
