"""
Technical Analysis Indicators for vnbroker.

Pure pandas/numpy implementations with zero external dependencies.
All functions accept pandas Series and return pandas Series/DataFrame.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def sma(series: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
    """
    Simple Moving Average (SMA).
    
    Args:
        series: Price series (typically close prices)
        window: Number of periods for the moving average
        min_periods: Minimum number of observations required (default: 1)
    
    Returns:
        pd.Series: SMA values with same index as input
    
    Example:
        >>> close = pd.Series([10, 11, 12, 13, 14])
        >>> sma(close, window=3)
        0     10.0
        1     10.5
        2     11.0
        3     12.0
        4     13.0
    """
    return series.rolling(window=window, min_periods=min_periods).mean()


def ema(series: pd.Series, window: int, adjust: bool = False) -> pd.Series:
    """
    Exponential Moving Average (EMA).
    
    Args:
        series: Price series (typically close prices)
        window: Number of periods for the EMA
        adjust: If True, uses recursive adjustment (default: False for standard EMA)
    
    Returns:
        pd.Series: EMA values with same index as input
    
    Example:
        >>> close = pd.Series([10, 11, 12, 13, 14])
        >>> ema(close, window=3)
    """
    return series.ewm(span=window, adjust=adjust).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """
    Relative Strength Index (RSI) using Wilder's Smoothing.
    
    Args:
        series: Price series (typically close prices)
        window: RSI period (default: 14)
    
    Returns:
        pd.Series: RSI values (0-100) with same index as input
    
    Example:
        >>> close = pd.Series([10, 11, 10.5, 11.5, 12, 11.8, 12.5])
        >>> rsi(close, window=14)
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Wilder's Smoothing (alpha = 1 / window)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False).mean()
    
    both_zero = (avg_gain == 0) & (avg_loss == 0)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100.0 - (100.0 / (1.0 + rs))
    
    # Handle division by zero (when avg_loss is 0, RSI = 100)
    rsi_values = rsi_values.fillna(100.0)
    # When price is completely flat (both gain and loss are 0), RSI is neutral (50.0)
    rsi_values = rsi_values.where(~both_zero, 50.0)
    
    return rsi_values


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Moving Average Convergence Divergence (MACD).
    
    Args:
        series: Price series (typically close prices)
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line EMA period (default: 9)
    
    Returns:
        tuple: (macd_line, signal_line, histogram) - all pd.Series with same index
    
    Example:
        >>> close = pd.Series([...])
        >>> macd_line, signal_line, histogram = macd(close)
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def bollinger_bands(
    series: pd.Series,
    window: int = 20,
    num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands.
    
    Args:
        series: Price series (typically close prices)
        window: SMA period for middle band (default: 20)
        num_std: Number of standard deviations for upper/lower bands (default: 2.0)
    
    Returns:
        tuple: (upper_band, middle_band, lower_band) - all pd.Series with same index
    
    Example:
        >>> close = pd.Series([...])
        >>> upper, middle, lower = bollinger_bands(close)
    """
    middle = sma(series, window)
    std = series.rolling(window=window, min_periods=1).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    
    return upper, middle, lower


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14
) -> pd.Series:
    """
    Average True Range (ATR) using Wilder's Smoothing.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        window: ATR period (default: 14)
    
    Returns:
        pd.Series: ATR values with same index as input
    """
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_values = true_range.ewm(alpha=1.0 / window, adjust=False).mean()
    
    return atr_values


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_window: int = 14,
    d_window: int = 3
) -> tuple[pd.Series, pd.Series]:
    """
    Stochastic Oscillator.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        k_window: %K period (default: 14)
        d_window: %D smoothing period (default: 3)
    
    Returns:
        tuple: (%K, %D) - both pd.Series with same index
    """
    lowest_low = low.rolling(window=k_window, min_periods=1).min()
    highest_high = high.rolling(window=k_window, min_periods=1).max()
    
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan))
    k_percent = k_percent.fillna(50)  # Neutral when high == low
    
    d_percent = k_percent.rolling(window=d_window, min_periods=1).mean()
    
    return k_percent, d_percent


def williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14
) -> pd.Series:
    """
    Williams %R.
    
    Args:
        high: High price series
        low: Low price series
        close: Close price series
        window: Lookback period (default: 14)
    
    Returns:
        pd.Series: Williams %R values (-100 to 0) with same index
    """
    highest_high = high.rolling(window=window, min_periods=1).max()
    lowest_low = low.rolling(window=window, min_periods=1).min()
    
    wr = -100 * ((highest_high - close) / (highest_high - lowest_low).replace(0, np.nan))
    wr = wr.fillna(-50)  # Neutral when high == low
    
    return wr


def cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 20
) -> pd.Series:
    """
    Commodity Channel Index (CCI) — vectorized, no rolling.apply.

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        window: CCI period (default: 20, must be > 0)

    Returns:
        pd.Series: CCI values with same index
    """
    if window <= 0:
        raise ValueError(f"window must be > 0. Got: {window}")
    typical_price = (high + low + close) / 3
    sma_tp = typical_price.rolling(window=window, min_periods=1).mean()
    # Vectorized mean absolute deviation (10-50x faster than rolling.apply)
    mean_dev = (typical_price - sma_tp).abs().rolling(window=window, min_periods=1).mean()

    cci_values = (typical_price - sma_tp) / (0.015 * mean_dev.replace(0, float("nan")))
    cci_values = cci_values.fillna(0)

    return cci_values


# Convenience function to compute multiple indicators at once
def compute_all_indicators(
    df: pd.DataFrame,
    price_col: str = 'close',
    high_col: str = 'high',
    low_col: str = 'low',
    volume_col: str = 'volume',
    indicators: list[str] | None = None,
) -> pd.DataFrame:
    """
    Compute selected indicators for a price DataFrame.

    Args:
        df: DataFrame with OHLCV columns
        price_col: Column name for close price
        high_col: Column name for high price
        low_col: Column name for low price
        volume_col: Column name for volume (reserved for future volume indicators)
        indicators: Subset to compute — any of
            ['sma','ema','rsi','macd','bb','atr','stoch','williams_r','cci'].
            None (default) computes all (backward-compatible).

    Returns:
        pd.DataFrame: Original DataFrame with indicator columns added
    """
    _ = volume_col
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("DataFrame cannot be empty or None")

    required_cols = [price_col, high_col, low_col]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in DataFrame: {missing_cols}")

    wanted = set(indicators) if indicators is not None else None
    valid = {'sma', 'ema', 'rsi', 'macd', 'bb', 'atr', 'stoch', 'williams_r', 'cci'}
    if wanted is not None:
        unknown = wanted - valid
        if unknown:
            raise ValueError(f"Unknown indicators: {sorted(unknown)}. Valid: {sorted(valid)}")

    def _want(name: str) -> bool:
        return wanted is None or name in wanted

    result = df.copy()
    close = df[price_col]
    high = df[high_col]
    low = df[low_col]

    # Trend indicators
    if _want('sma'):
        result['sma_20'] = sma(close, 20)
        result['sma_50'] = sma(close, 50)
    if _want('ema'):
        result['ema_12'] = ema(close, 12)
        result['ema_26'] = ema(close, 26)

    # Momentum indicators
    if _want('rsi'):
        result['rsi_14'] = rsi(close, 14)

    # MACD
    if _want('macd'):
        macd_line, signal_line, histogram = macd(close)
        result['macd'] = macd_line
        result['macd_signal'] = signal_line
        result['macd_hist'] = histogram

    # Bollinger Bands
    if _want('bb'):
        upper, middle, lower = bollinger_bands(close)
        result['bb_upper'] = upper
        result['bb_middle'] = middle
        result['bb_lower'] = lower
        result['bb_width'] = (upper - lower) / middle.replace(0, np.nan)
        result['bb_pct'] = (close - lower) / (upper - lower).replace(0, np.nan)

    # Volatility
    if _want('atr'):
        result['atr_14'] = atr(high, low, close, 14)

    # Stochastic
    if _want('stoch'):
        k_pct, d_pct = stochastic(high, low, close)
        result['stoch_k'] = k_pct
        result['stoch_d'] = d_pct

    # Williams %R
    if _want('williams_r'):
        result['williams_r'] = williams_r(high, low, close)

    # CCI
    if _want('cci'):
        result['cci_20'] = cci(high, low, close)

    return result


__all__ = [
    'sma',
    'ema',
    'rsi',
    'macd',
    'bollinger_bands',
    'atr',
    'stochastic',
    'williams_r',
    'cci',
    'compute_all_indicators',
]