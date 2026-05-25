from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DailySnapshot:
    prev_close: float
    prev_high: float
    prev_low: float
    prev_open: float
    ret_5: float
    ret_20: float
    atr_pct_14: float
    avg_amount_20: float
    ma5_distance: float
    ma10_distance: float
    ma20_distance: float
    position_20: float
    upper_shadow_ratio: float
    lower_shadow_ratio: float
    close_position: float


@dataclass(frozen=True)
class IntradaySnapshot:
    signal_date: date
    decision_time: str
    current_price: float
    day_open: float
    morning_high: float
    morning_low: float
    morning_close: float
    morning_amount: float
    vwap: float
    open_gap: float
    first_return: float
    morning_range_pct: float
    vwap_distance: float
    amount_ratio: float
    close_position: float
    reclaimed_vwap: bool
    broke_prev_low: bool
    broke_prev_high: bool


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0 or np.isnan(b):
        return default
    return float(a / b)


def _shadow_ratios(row: pd.Series) -> tuple[float, float, float]:
    high = float(row["high"])
    low = float(row["low"])
    open_ = float(row["open"])
    close = float(row["close"])
    span = max(high - low, 1e-9)
    upper = high - max(open_, close)
    lower = min(open_, close) - low
    close_pos = (close - low) / span
    return upper / span, lower / span, close_pos


def compute_daily_snapshot(daily: pd.DataFrame, before_date: Optional[date] = None) -> DailySnapshot:
    if before_date is not None:
        hist = daily[daily["date"] < before_date].copy()
    else:
        hist = daily.copy()
    if len(hist) < 25:
        raise ValueError("Need at least 25 daily bars to compute stable features")

    hist = hist.sort_values("date").reset_index(drop=True)
    row = hist.iloc[-1]
    close = hist["close"]
    high = hist["high"]
    low = hist["low"]
    prev_close = float(row["close"])
    prev_high = float(row["high"])
    prev_low = float(row["low"])

    prev_close_series = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close_series).abs(),
            (low - prev_close_series).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = float(tr.rolling(14).mean().iloc[-1])

    high20 = float(high.tail(20).max())
    low20 = float(low.tail(20).min())
    ma5 = float(close.tail(5).mean())
    ma10 = float(close.tail(10).mean())
    ma20 = float(close.tail(20).mean())
    upper, lower, close_pos = _shadow_ratios(row)

    return DailySnapshot(
        prev_close=prev_close,
        prev_high=prev_high,
        prev_low=prev_low,
        prev_open=float(row["open"]),
        ret_5=_safe_div(prev_close, float(close.iloc[-6])) - 1.0,
        ret_20=_safe_div(prev_close, float(close.iloc[-21])) - 1.0,
        atr_pct_14=_safe_div(atr14, prev_close),
        avg_amount_20=float(hist["amount"].tail(20).mean()),
        ma5_distance=_safe_div(prev_close, ma5) - 1.0,
        ma10_distance=_safe_div(prev_close, ma10) - 1.0,
        ma20_distance=_safe_div(prev_close, ma20) - 1.0,
        position_20=_safe_div(prev_close - low20, high20 - low20, 0.5),
        upper_shadow_ratio=float(upper),
        lower_shadow_ratio=float(lower),
        close_position=float(close_pos),
    )


def compute_intraday_snapshot(
    minute: pd.DataFrame,
    daily_snapshot: DailySnapshot,
    decision_time: str = "09:35",
    signal_date: Optional[date] = None,
) -> IntradaySnapshot:
    minute = minute.sort_values("datetime")
    if signal_date is None:
        signal_date = minute["date"].max()
    day = minute[minute["date"] == signal_date].copy()
    if day.empty:
        raise ValueError(f"No minute bars for {signal_date}")

    window = day[day["time"] <= decision_time].copy()
    if window.empty:
        window = day.head(1).copy()

    first = day.iloc[0]
    last = window.iloc[-1]
    amount_sum = float(window["amount"].sum())
    volume_sum = float(window["volume"].sum())
    if amount_sum > 0 and volume_sum > 0:
        vwap = amount_sum / volume_sum
    else:
        vwap = float((window["close"] * window["volume"]).sum() / max(volume_sum, 1.0))

    morning_high = float(window["high"].max())
    morning_low = float(window["low"].min())
    current = float(last["close"])
    span = max(morning_high - morning_low, 1e-9)

    return IntradaySnapshot(
        signal_date=signal_date,
        decision_time=str(last["time"]),
        current_price=current,
        day_open=float(first["open"]),
        morning_high=morning_high,
        morning_low=morning_low,
        morning_close=current,
        morning_amount=amount_sum,
        vwap=float(vwap),
        open_gap=_safe_div(float(first["open"]), daily_snapshot.prev_close) - 1.0,
        first_return=_safe_div(current, float(first["open"])) - 1.0,
        morning_range_pct=_safe_div(morning_high - morning_low, daily_snapshot.prev_close),
        vwap_distance=_safe_div(current, float(vwap)) - 1.0,
        amount_ratio=_safe_div(amount_sum, daily_snapshot.avg_amount_20),
        close_position=(current - morning_low) / span,
        reclaimed_vwap=morning_low < vwap <= current,
        broke_prev_low=morning_low < daily_snapshot.prev_low,
        broke_prev_high=morning_high > daily_snapshot.prev_high,
    )


def estimate_market_return(index_daily: Optional[pd.DataFrame], as_of: Optional[date] = None) -> float:
    if index_daily is None or len(index_daily) < 2:
        return 0.0
    df = index_daily.sort_values("date").copy()
    if as_of is not None:
        df = df[df["date"] <= as_of]
    if len(df) < 2:
        return 0.0
    return float(df["close"].iloc[-1] / df["close"].iloc[-2] - 1.0)


def estimate_market_breadth_score(
    index_daily: Optional[pd.DataFrame] = None,
    as_of: Optional[date] = None,
    limit_up: int = 0,
    limit_down: int = 0,
    advance: int = 0,
    decline: int = 0,
    total: int = 0,
) -> float:
    """Compute a composite market breadth score combining index return and breadth data."""
    ret = estimate_market_return(index_daily, as_of)
    score = 1.2

    if ret >= 0.008:
        score = 2.0
    elif ret >= 0:
        score = 1.7
    elif ret >= -0.008:
        score = 1.0
    else:
        score = 0.4

    if limit_up > 0 or limit_down > 0:
        breadth_bonus = 0.0
        if limit_up >= 80:
            breadth_bonus = 0.8
        elif limit_up >= 50:
            breadth_bonus = 0.5
        elif limit_up >= 25:
            breadth_bonus = 0.3
        elif limit_up >= 10:
            breadth_bonus = 0.1
        else:
            breadth_bonus = -0.2

        if limit_down >= 50:
            breadth_bonus -= 0.6
        elif limit_down >= 20:
            breadth_bonus -= 0.3

        if total > 0:
            ad_ratio = advance / max(decline, 1)
            if ad_ratio >= 3.0:
                breadth_bonus += 0.2
            elif ad_ratio <= 0.33:
                breadth_bonus -= 0.2

        score += breadth_bonus

    return max(0.0, min(3.0, score))

