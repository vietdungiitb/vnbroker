import pandas as pd
import pytest

from vnbroker.analytics.indicators import (
    rsi,
    atr,
    compute_all_indicators,
)


@pytest.mark.unit
def test_rsi_wilder_flat_price():
    # When price is completely flat, RSI should be 50.0
    series = pd.Series([100.0] * 30)
    rsi_vals = rsi(series, window=14)
    assert (rsi_vals == 50.0).all()


@pytest.mark.unit
def test_rsi_strictly_increasing():
    # When price is strictly increasing, RSI should be 100.0
    series = pd.Series([10.0 + i for i in range(25)])
    rsi_vals = rsi(series, window=14)
    # Beyond index 0, RSI should be 100
    assert (rsi_vals.iloc[1:] == 100.0).all()


@pytest.mark.unit
def test_rsi_strictly_decreasing():
    # When price is strictly decreasing, RSI should be 0.0
    series = pd.Series([100.0 - i for i in range(25)])
    rsi_vals = rsi(series, window=14)
    assert (rsi_vals.iloc[1:] == 0.0).all()


@pytest.mark.unit
def test_rsi_wilder_smoothing_behavior():
    # Fluctuating prices: verify values stay in [0, 100]
    prices = pd.Series([10, 11, 10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16, 18, 17, 19, 18, 20])
    rsi_vals = rsi(prices, window=14)
    assert len(rsi_vals) == len(prices)
    assert ((rsi_vals >= 0.0) & (rsi_vals <= 100.0)).all()
    # Trending up overall, RSI should be > 50 towards end
    assert rsi_vals.iloc[-1] > 50.0


@pytest.mark.unit
def test_atr_wilder():
    high = pd.Series([10, 12, 14, 13, 15, 16, 17, 18, 19, 20])
    low = pd.Series([9, 10, 12, 11, 13, 14, 15, 16, 17, 18])
    close = pd.Series([9.5, 11, 13, 12, 14, 15, 16, 17, 18, 19])
    
    atr_vals = atr(high, low, close, window=5)
    assert len(atr_vals) == len(high)
    assert (atr_vals > 0).all()


@pytest.mark.unit
def test_compute_all_indicators_empty_df():
    with pytest.raises(ValueError, match="DataFrame cannot be empty"):
        compute_all_indicators(pd.DataFrame())


@pytest.mark.unit
def test_compute_all_indicators_missing_columns():
    df = pd.DataFrame({"close": [10, 11, 12]})
    with pytest.raises(ValueError, match="Missing required columns"):
        compute_all_indicators(df)


@pytest.mark.unit
def test_compute_all_indicators_valid():
    df = pd.DataFrame({
        "close": [10.0 + i * 0.5 for i in range(60)],
        "high": [11.0 + i * 0.5 for i in range(60)],
        "low": [9.5 + i * 0.5 for i in range(60)],
        "volume": [1000 + i * 10 for i in range(60)]
    })
    res = compute_all_indicators(df)
    for col in ["sma_20", "sma_50", "ema_12", "ema_26", "rsi_14", "macd", "macd_signal", "macd_hist", "bb_upper", "bb_middle", "bb_lower", "atr_14", "stoch_k", "stoch_d", "williams_r", "cci_20"]:
        assert col in res.columns
