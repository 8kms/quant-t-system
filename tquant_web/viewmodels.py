from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import pandas as pd

from tquant.config import AppConfig
from tquant.core.execution_plan import build_execution_plan_for_item
from tquant.core.features import compute_daily_snapshot, compute_intraday_snapshot
from tquant.io import WatchItem, load_daily, load_minute, load_watchlist, normalize_symbol
from tquant.core.signals import TSignalEngine
from tquant.workflow import read_latest_csv


def line_points(values: Iterable[float], width: int = 760, height: int = 220) -> str:
    series = [float(value) for value in values if pd.notna(value)]
    if not series:
        return ""
    if len(series) == 1:
        return f"0,{height / 2:.2f} {width},{height / 2:.2f}"
    low = min(series)
    high = max(series)
    span = high - low if high != low else 1.0
    points = []
    for idx, value in enumerate(series):
        x = width * idx / (len(series) - 1)
        y = height - ((value - low) / span * height)
        points.append(f"{x:.2f},{y:.2f}")
    return " ".join(points)


def last_signal_for(config: AppConfig, symbol: str) -> Dict[str, object]:
    signals = read_latest_csv(config.data.output_dir, "signals_*.csv")
    if signals.empty or "symbol" not in signals.columns:
        return {}
    rows = signals[signals["symbol"].map(normalize_symbol) == normalize_symbol(symbol)]
    if rows.empty:
        return {}
    return rows.fillna("").iloc[0].to_dict()


def last_profile_for(config: AppConfig, symbol: str) -> Dict[str, object]:
    profiles = read_latest_csv(config.data.output_dir, "stock_profiles_*.csv")
    if profiles.empty or "symbol" not in profiles.columns:
        return {}
    rows = profiles[profiles["symbol"].map(normalize_symbol) == normalize_symbol(symbol)]
    if rows.empty:
        return {}
    return rows.fillna("").iloc[0].to_dict()


def find_watch_item(config: AppConfig, symbol: str) -> Optional[WatchItem]:
    target = normalize_symbol(symbol)
    for item in load_watchlist(config.data.watchlist_path):
        if item.symbol == target:
            return item
    return None


def build_stock_detail(config: AppConfig, symbol: str) -> Dict[str, object]:
    symbol = normalize_symbol(symbol)
    item = find_watch_item(config, symbol) or WatchItem(symbol=symbol)
    daily = load_daily(symbol, config.data.daily_dir)
    minute = load_minute(symbol, config.data.minute_dir)
    latest_minute_date = minute["date"].max()
    day_minute = minute[minute["date"] == latest_minute_date].copy()
    day_minute["cum_volume"] = day_minute["volume"].cumsum()
    day_minute["cum_amount"] = day_minute["amount"].cumsum()
    day_minute["vwap"] = day_minute["cum_amount"] / day_minute["cum_volume"].replace(0, pd.NA)

    daily_snapshot = compute_daily_snapshot(daily, before_date=latest_minute_date)
    intraday_snapshot = compute_intraday_snapshot(
        minute,
        daily_snapshot,
        decision_time=config.signals.decision_time,
        signal_date=latest_minute_date,
    )
    signal = TSignalEngine(config.costs, config.signals).generate(
        item,
        daily_snapshot,
        intraday_snapshot,
    )
    try:
        plan = build_execution_plan_for_item(item, config)
    except Exception:
        plan = None

    daily_tail = daily.tail(80).copy()
    minute_tail = day_minute.copy()
    daily_points = line_points(daily_tail["close"])
    minute_points = line_points(minute_tail["close"])
    vwap_points = line_points(minute_tail["vwap"].ffill().fillna(minute_tail["close"]))

    factor_rows = [
        ("开盘缺口", intraday_snapshot.open_gap, "pct"),
        ("当前价偏离VWAP", intraday_snapshot.vwap_distance, "pct"),
        ("早盘区间位置", intraday_snapshot.close_position, "pct"),
        ("早盘成交额/20日均额", intraday_snapshot.amount_ratio, "pct"),
        ("近5日涨幅", daily_snapshot.ret_5, "pct"),
        ("近20日涨幅", daily_snapshot.ret_20, "pct"),
        ("ATR14/收盘价", daily_snapshot.atr_pct_14, "pct"),
        ("20日区间位置", daily_snapshot.position_20, "pct"),
        ("昨日上影线比例", daily_snapshot.upper_shadow_ratio, "pct"),
        ("昨日下影线比例", daily_snapshot.lower_shadow_ratio, "pct"),
    ]

    realtime_price = intraday_snapshot.current_price
    realtime_change = 0.0
    realtime_pe = 0.0
    realtime_pb = 0.0
    realtime_mcap = 0.0
    try:
        from tquant.data.stable_provider import fetch_realtime_quote, fetch_tencent_quotes
        rt = fetch_realtime_quote(symbol)
        if rt and rt.get("price", 0) > 0:
            realtime_price = float(rt["price"])
            realtime_change = float(rt.get("change", 0))
        tx = fetch_tencent_quotes([symbol])
        if symbol in tx:
            realtime_pe = float(tx[symbol].get("pe_ttm", 0))
            realtime_pb = float(tx[symbol].get("pb", 0))
            realtime_mcap = float(tx[symbol].get("mcap_yi", 0))
    except Exception:
        pass

    return {
        "item": item,
        "signal": signal,
        "plan": plan,
        "latest_signal": last_signal_for(config, symbol),
        "profile": last_profile_for(config, symbol),
        "daily": daily_tail.sort_values("date", ascending=False).head(20),
        "minute": minute_tail.sort_values("datetime", ascending=False).head(40),
        "daily_chart": daily_points,
        "minute_chart": minute_points,
        "vwap_chart": vwap_points,
        "daily_min": float(daily_tail["close"].min()),
        "daily_max": float(daily_tail["close"].max()),
        "minute_min": float(minute_tail["close"].min()),
        "minute_max": float(minute_tail["close"].max()),
        "factor_rows": factor_rows,
        "signal_date": latest_minute_date,
        "decision_time": intraday_snapshot.decision_time,
        "vwap": intraday_snapshot.vwap,
        "current_price": realtime_price,
        "realtime_change": realtime_change,
        "realtime_pe": realtime_pe,
        "realtime_pb": realtime_pb,
        "realtime_mcap": realtime_mcap,
    }
