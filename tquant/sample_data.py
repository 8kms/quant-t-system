from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .io import save_dataframe


def _trading_minutes(day) -> list[datetime]:
    minutes = []
    start = datetime.combine(day, datetime.strptime("09:30", "%H:%M").time())
    for i in range(120):
        minutes.append(start + timedelta(minutes=i))
    start_pm = datetime.combine(day, datetime.strptime("13:00", "%H:%M").time())
    for i in range(120):
        minutes.append(start_pm + timedelta(minutes=i))
    return minutes


def generate_sample_dataset(
    symbols: Iterable[str],
    daily_dir: Path,
    minute_dir: Path,
    index_daily_dir: Path,
    watchlist_path: Path,
    seed: int = 7,
) -> None:
    rng = np.random.default_rng(seed)
    daily_dir.mkdir(parents=True, exist_ok=True)
    minute_dir.mkdir(parents=True, exist_ok=True)
    index_daily_dir.mkdir(parents=True, exist_ok=True)
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)

    start = pd.Timestamp("2025-01-02")
    business_days = pd.bdate_range(start, periods=120)
    watch_rows = []
    for idx, symbol in enumerate(symbols):
        target_daily = daily_dir / f"{symbol}.csv"
        target_minute = minute_dir / f"{symbol}.csv"
        if target_daily.exists() and target_minute.exists():
            continue

        base = 10 + idx * 8
        daily_rows = []
        close = base
        for day in business_days:
            drift = 0.0004 + idx * 0.0001
            vol = 0.018 + idx * 0.003
            overnight = rng.normal(drift, vol / 2)
            open_ = close * (1 + overnight)
            intraday = rng.normal(drift, vol)
            close = max(1.0, open_ * (1 + intraday))
            high = max(open_, close) * (1 + abs(rng.normal(0.006, 0.004)))
            low = min(open_, close) * (1 - abs(rng.normal(0.006, 0.004)))
            volume = int(rng.integers(2_000_000, 12_000_000))
            amount = volume * close
            daily_rows.append(
                {
                    "date": day.date(),
                    "open": round(open_, 3),
                    "high": round(high, 3),
                    "low": round(low, 3),
                    "close": round(close, 3),
                    "volume": volume,
                    "amount": round(amount, 2),
                }
            )
        daily = pd.DataFrame(daily_rows)
        save_dataframe(daily, target_daily)

        minute_rows = []
        for day in business_days[-35:]:
            prev_close = float(daily[daily["date"] < day.date()]["close"].iloc[-1])
            gap = rng.normal(0, 0.012)
            current = prev_close * (1 + gap)
            minutes = _trading_minutes(day.date())
            trend = rng.normal(0, 0.006)
            for i, dt in enumerate(minutes):
                if i == 0:
                    open_ = current
                else:
                    open_ = current
                shock = rng.normal(trend / len(minutes), 0.0028)
                close_m = max(1.0, open_ * (1 + shock))
                high = max(open_, close_m) * (1 + abs(rng.normal(0.0009, 0.0005)))
                low = min(open_, close_m) * (1 - abs(rng.normal(0.0009, 0.0005)))
                volume = int(rng.integers(6_000, 60_000))
                amount = volume * close_m
                minute_rows.append(
                    {
                        "datetime": dt,
                        "open": round(open_, 3),
                        "high": round(high, 3),
                        "low": round(low, 3),
                        "close": round(close_m, 3),
                        "volume": volume,
                        "amount": round(amount, 2),
                    }
                )
                current = close_m
        save_dataframe(pd.DataFrame(minute_rows), target_minute)
        watch_rows.append(
            {
                "symbol": symbol,
                "name": f"Sample{idx + 1}",
                "sector": "Sample",
                "base_position": 1000,
                "avg_cost": round(base, 3),
            }
        )

    index_target = index_daily_dir / "000001.csv"
    if not index_target.exists():
        index_close = 3000.0
        index_rows = []
        for day in business_days:
            open_ = index_close * (1 + rng.normal(0, 0.003))
            index_close = max(2000.0, open_ * (1 + rng.normal(0, 0.006)))
            high = max(open_, index_close) * 1.003
            low = min(open_, index_close) * 0.997
            index_rows.append(
                {
                    "date": day.date(),
                    "open": round(open_, 3),
                    "high": round(high, 3),
                    "low": round(low, 3),
                    "close": round(index_close, 3),
                    "volume": 1,
                    "amount": 1,
                }
            )
        save_dataframe(pd.DataFrame(index_rows), index_target)

    if not watchlist_path.exists():
        save_dataframe(pd.DataFrame(watch_rows), watchlist_path)
