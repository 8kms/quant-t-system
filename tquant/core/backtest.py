from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional

import pandas as pd

from ..config import AppConfig
from .features import compute_daily_snapshot, compute_intraday_snapshot
from ..io import WatchItem
from .signals import TSignal, TSignalEngine


@dataclass(frozen=True)
class BacktestResult:
    trades: pd.DataFrame
    summary: pd.DataFrame
    by_symbol: pd.DataFrame
    by_action: pd.DataFrame
    by_year: pd.DataFrame


def _simulate_trade(
    signal: TSignal,
    day_after_decision: pd.DataFrame,
    round_trip_cost: float,
) -> Dict[str, object]:
    entry = signal.observe_price
    target = signal.target_price
    cancel = signal.cancel_price
    action = signal.action

    if action == "hold" or day_after_decision.empty:
        return {
            "success": False,
            "exit_price": entry,
            "exit_reason": "hold",
            "net_return": 0.0,
        }

    exit_price = float(day_after_decision["close"].iloc[-1])
    exit_reason = "eod"
    success = False

    for _, row in day_after_decision.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        if action == "reverse_t":
            if high >= cancel:
                exit_price = cancel
                exit_reason = "cancel_sell_fly"
                break
            if low <= target:
                exit_price = target
                exit_reason = "target_buyback"
                success = True
                break
        elif action == "positive_t":
            if low <= cancel:
                exit_price = cancel
                exit_reason = "stop_loss"
                break
            if high >= target:
                exit_price = target
                exit_reason = "target_sell"
                success = True
                break

    if action == "reverse_t":
        gross = (entry - exit_price) / entry
    else:
        gross = (exit_price - entry) / entry
    net = gross - round_trip_cost
    return {
        "success": bool(success),
        "exit_price": round(exit_price, 3),
        "exit_reason": exit_reason,
        "net_return": round(float(net), 6),
    }


def _aggregate(df: pd.DataFrame, group_cols: Optional[List[str]] = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    if group_cols is None:
        grouped = [((), df)]
    else:
        grouped = df.groupby(group_cols, dropna=False)

    rows = []
    for key, part in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        row: Dict[str, object] = {}
        if group_cols is not None:
            row.update(dict(zip(group_cols, key)))
        row.update(
            {
                "trades": int(len(part)),
                "success_rate": round(float(part["success"].mean()), 4),
                "avg_net_return": round(float(part["net_return"].mean()), 5),
                "median_net_return": round(float(part["net_return"].median()), 5),
                "total_net_return": round(float(part["net_return"].sum()), 5),
                "avg_score": round(float(part["score"].mean()), 2),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def run_backtest_for_items(
    items: Iterable[WatchItem],
    daily_map: Dict[str, pd.DataFrame],
    minute_map: Dict[str, pd.DataFrame],
    config: AppConfig,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> BacktestResult:
    engine = TSignalEngine(config.costs, config.signals)
    trade_rows: List[Dict[str, object]] = []

    for item in items:
        daily = daily_map[item.symbol]
        minute = minute_map[item.symbol]
        dates = sorted(minute["date"].unique())
        for signal_date in dates:
            if start is not None and signal_date < start:
                continue
            if end is not None and signal_date > end:
                continue
            try:
                daily_snapshot = compute_daily_snapshot(daily, before_date=signal_date)
                intra_snapshot = compute_intraday_snapshot(
                    minute,
                    daily_snapshot,
                    decision_time=config.signals.decision_time,
                    signal_date=signal_date,
                )
            except ValueError:
                continue

            signal = engine.generate(item, daily_snapshot, intra_snapshot)
            day = minute[minute["date"] == signal_date]
            after = day[day["time"] > intra_snapshot.decision_time]
            sim = _simulate_trade(signal, after, config.costs.round_trip_rate)
            trade_rows.append(
                {
                    "date": signal_date,
                    "year": str(signal_date)[:4],
                    "symbol": item.symbol,
                    "name": item.name,
                    "action": signal.action,
                    "score": signal.score,
                    "confidence": signal.confidence,
                    "observe_price": signal.observe_price,
                    "target_price": signal.target_price,
                    "cancel_price": signal.cancel_price,
                    **sim,
                }
            )

    trades = pd.DataFrame(trade_rows)
    if trades.empty:
        return BacktestResult(
            trades=trades,
            summary=pd.DataFrame(),
            by_symbol=pd.DataFrame(),
            by_action=pd.DataFrame(),
            by_year=pd.DataFrame(),
        )

    active = trades[trades["action"] != "hold"].copy()
    return BacktestResult(
        trades=trades,
        summary=_aggregate(active),
        by_symbol=_aggregate(active, ["symbol", "name"]),
        by_action=_aggregate(active, ["action"]),
        by_year=_aggregate(active, ["year"]),
    )

