"""
vnbroker.analytics - Advanced Analytics & ML Module

Provides technical indicators, ML signal generation, backtesting,
portfolio optimization, and factor modeling capabilities.
"""

from vnbroker.analytics.indicators import (
    TechnicalIndicators,
    add_all_indicators,
    SMA,
    EMA,
    RSI,
    MACD,
    BollingerBands,
    ATR,
    Stochastic,
    WilliamsR,
    CCI,
    ADX,
    OBV,
    VWAP,
)

from vnbroker.analytics.signals import (
    SignalGenerator,
    MLSignalGenerator,
    Signal,
    SignalType,
)

from vnbroker.analytics.backtest import (
    BacktestEngine,
    BacktestResult,
    WalkForwardValidator,
    Strategy,
)

from vnbroker.analytics.portfolio import (
    PortfolioOptimizer,
    MeanVarianceOptimizer,
    RiskParityOptimizer,
    BlackLittermanOptimizer,
    PortfolioResult,
)

from vnbroker.analytics.factors import (
    FactorModel,
    RiskAttribution,
    FactorAnalysis,
)

__all__ = [
    # Indicators
    "TechnicalIndicators",
    "add_all_indicators",
    "SMA",
    "EMA",
    "RSI",
    "MACD",
    "BollingerBands",
    "ATR",
    "Stochastic",
    "WilliamsR",
    "CCI",
    "ADX",
    "OBV",
    "VWAP",
    # Signals
    "SignalGenerator",
    "MLSignalGenerator",
    "Signal",
    "SignalType",
    # Backtesting
    "BacktestEngine",
    "BacktestResult",
    "WalkForwardValidator",
    "Strategy",
    # Portfolio
    "PortfolioOptimizer",
    "MeanVarianceOptimizer",
    "RiskParityOptimizer",
    "BlackLittermanOptimizer",
    "PortfolioResult",
    # Factors
    "FactorModel",
    "RiskAttribution",
    "FactorAnalysis",
]
