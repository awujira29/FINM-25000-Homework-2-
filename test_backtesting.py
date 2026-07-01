"""
test_backtesting.py
Unit tests for indicators, strategies, the backtest engine, and metrics.
Uses synthetic OHLCV data (no network / Alpaca credentials required).

Kept separate from test_connector.py, which covers the live Alpaca
connector and does require credentials.
"""

import numpy as np
import pandas as pd
import pytest

from indicators import sma, ema, macd, rsi, bollinger_bands, atr, adx, obv, add_all_indicators
from strategies import trend_following_strategy, mean_reversion_strategy, custom_strategy
from backtest import Backtester
import metrics as m


@pytest.fixture
def synthetic_df():
    """~3 years of synthetic daily OHLCV data with a random-walk-plus-drift close."""
    rng = np.random.default_rng(42)
    n = 750
    dates = pd.date_range("2021-01-04", periods=n, freq="B")

    returns = rng.normal(loc=0.0004, scale=0.015, size=n)
    close = 100 * np.cumprod(1 + returns)

    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    volume = rng.integers(1_000_000, 5_000_000, n)

    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    return df


# --------------------------------------------------------------------------
# Indicators
# --------------------------------------------------------------------------

def test_sma_matches_pandas_rolling_mean(synthetic_df):
    result = sma(synthetic_df["Close"], 20)
    expected = synthetic_df["Close"].rolling(20).mean()
    pd.testing.assert_series_equal(result, expected, check_names=False)


def test_ema_reduces_to_seed_after_warmup(synthetic_df):
    result = ema(synthetic_df["Close"], 10)
    assert result.isna().sum() == 9  # min_periods warm-up
    assert result.iloc[-1] > 0


def test_macd_returns_three_series_same_length(synthetic_df):
    macd_line, signal_line, hist = macd(synthetic_df["Close"])
    assert len(macd_line) == len(synthetic_df)
    np.testing.assert_allclose(
        (macd_line - signal_line).dropna(), hist.dropna(), rtol=1e-9
    )


def test_rsi_bounded_between_0_and_100(synthetic_df):
    result = rsi(synthetic_df["Close"]).dropna()
    assert (result >= 0).all() and (result <= 100).all()


def test_bollinger_bands_ordering(synthetic_df):
    upper, mid, lower = bollinger_bands(synthetic_df["Close"])
    valid = upper.dropna().index
    assert (upper.loc[valid] >= mid.loc[valid]).all()
    assert (mid.loc[valid] >= lower.loc[valid]).all()


def test_atr_non_negative(synthetic_df):
    result = atr(synthetic_df).dropna()
    assert (result >= 0).all()


def test_adx_bounded_between_0_and_100(synthetic_df):
    result = adx(synthetic_df).dropna()
    assert (result >= 0).all() and (result <= 100).all()


def test_obv_starts_from_zero_change_and_is_cumulative(synthetic_df):
    result = obv(synthetic_df)
    diffs = result.diff().dropna()
    volume_matches_sign = np.sign(synthetic_df["Close"].diff().dropna())
    nonzero = volume_matches_sign[volume_matches_sign != 0].index
    assert (np.sign(diffs.loc[nonzero]) == volume_matches_sign.loc[nonzero]).all()


def test_add_all_indicators_adds_expected_columns(synthetic_df):
    out = add_all_indicators(synthetic_df)
    expected_cols = {
        "SMA_20", "SMA_50", "EMA_20", "EMA_50", "EMA_200",
        "MACD", "MACD_Signal", "MACD_Hist", "ADX", "RSI",
        "BB_Upper", "BB_Mid", "BB_Lower", "ATR", "OBV", "OBV_SMA_20",
    }
    assert expected_cols.issubset(out.columns)


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------

@pytest.mark.parametrize("strategy_fn", [
    trend_following_strategy, mean_reversion_strategy, custom_strategy,
])
def test_strategy_signal_is_binary(synthetic_df, strategy_fn):
    out = strategy_fn(synthetic_df)
    assert set(out["Signal"].unique()).issubset({0, 1})


@pytest.mark.parametrize("strategy_fn", [
    trend_following_strategy, mean_reversion_strategy, custom_strategy,
])
def test_strategy_does_not_mutate_input(synthetic_df, strategy_fn):
    original = synthetic_df.copy()
    strategy_fn(synthetic_df)
    pd.testing.assert_frame_equal(synthetic_df, original)


# --------------------------------------------------------------------------
# Backtest engine
# --------------------------------------------------------------------------

def test_backtester_flat_signal_preserves_capital(synthetic_df):
    df = synthetic_df.copy()
    df["Signal"] = 0
    bt = Backtester(df, initial_capital=100_000)
    results = bt.run()
    assert np.isclose(results["Portfolio_Value"].iloc[-1], 100_000)


def test_backtester_always_long_matches_buy_and_hold(synthetic_df):
    df = synthetic_df.copy()
    df["Signal"] = 1
    bt = Backtester(df, initial_capital=100_000)
    results = bt.run()

    bh = Backtester.buy_and_hold(synthetic_df, initial_capital=100_000)

    assert np.isclose(
        results["Portfolio_Value"].iloc[-1],
        bh["Portfolio_Value"].iloc[-1],
        rtol=0.01,
    )


def test_backtester_signal_shift_avoids_lookahead(synthetic_df):
    """A signal flipped on the very last day should NOT affect that day's return."""
    df = synthetic_df.copy()
    df["Signal"] = 0
    df.loc[df.index[-1], "Signal"] = 1
    bt = Backtester(df, initial_capital=100_000)
    results = bt.run()
    assert results["Position"].iloc[-1] == 0


def test_backtester_produces_trade_log(synthetic_df):
    out = mean_reversion_strategy(synthetic_df)
    bt = Backtester(out, initial_capital=100_000)
    bt.run()
    assert bt.trades is not None
    if not bt.trades.empty:
        assert {"Entry_Date", "Exit_Date", "Return_Pct", "Win"}.issubset(bt.trades.columns)


def test_commission_reduces_terminal_value(synthetic_df):
    df = trend_following_strategy(synthetic_df)
    no_fee = Backtester(df, commission_bps=0).run()["Portfolio_Value"].iloc[-1]
    with_fee = Backtester(df, commission_bps=50).run()["Portfolio_Value"].iloc[-1]
    assert with_fee <= no_fee


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def test_metrics_on_flat_zero_vol_series():
    dates = pd.date_range("2022-01-01", periods=252, freq="B")
    portfolio_value = pd.Series(100_000.0, index=dates)
    daily_returns = pd.Series(0.0, index=dates)

    result = m.compute_all_metrics(daily_returns, portfolio_value)
    assert result["Total Return"] == 0
    assert np.isclose(result["CAGR"], 0, atol=1e-6)
    assert result["Max Drawdown"] == 0


def test_max_drawdown_is_negative_or_zero(synthetic_df):
    bh = Backtester.buy_and_hold(synthetic_df)
    dd = m.max_drawdown(bh["Portfolio_Value"])
    assert dd <= 0


def test_sharpe_ratio_finite_for_synthetic_data(synthetic_df):
    bh = Backtester.buy_and_hold(synthetic_df)
    sharpe = m.sharpe_ratio(bh["Daily_Return"])
    assert np.isfinite(sharpe)


def test_win_rate_between_0_and_1(synthetic_df):
    out = mean_reversion_strategy(synthetic_df)
    bt = Backtester(out)
    bt.run()
    wr = m.win_rate(bt.trades)
    if not np.isnan(wr):
        assert 0 <= wr <= 1
