from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def pivot_highs(df: pd.DataFrame, window: int) -> pd.Series:
    highs = df["high"]
    rolling_max = highs.rolling(window * 2 + 1, center=True).max()
    return highs.where(np.isclose(highs, rolling_max, equal_nan=False))


def pivot_lows(df: pd.DataFrame, window: int) -> pd.Series:
    lows = df["low"]
    rolling_min = lows.rolling(window * 2 + 1, center=True).min()
    return lows.where(np.isclose(lows, rolling_min, equal_nan=False))


def prepare_rates_frame(rates: list[dict] | np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame(rates)
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    numeric_cols = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"])
