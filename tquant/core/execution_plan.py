from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import pandas as pd

from ..config import AppConfig
from .features import compute_daily_snapshot, compute_intraday_snapshot, estimate_market_return
from ..io import WatchItem, load_daily, load_minute, load_watchlist, maybe_load_daily, normalize_symbol
from ..workflow import read_latest_csv
from ..data.corporate_actions import get_corp_action_risk_flags


@dataclass(frozen=True)
class ExecutionPlan:
    symbol: str
    name: str
    sector: str
    signal_date: str
    suitability_score: float
    recommendation: str
    trade_ratio: float
    primary_strategy: str
    sell_ref_1: float
    sell_ref_2: float
    buy_ref_vwap: float
    buy_ref_ma: float
    buy_ref_atr: float
    stop_buyback: float
    force_buyback_time: str
    atr_pct_14: float
    high_gap_pullback_rate: float
    avg_amount_20: float
    risk_flags: str
    status: str = "可用"


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(float(value), upper))


def _score_by_range(value: float, low: float, high: float, max_score: float) -> float:
    if value <= low:
        return 0.0
    if value >= high:
        return max_score
    return (value - low) / (high - low) * max_score


def _recommendation(score: float) -> tuple[str, float]:
    if score >= 8:
        return "积极做T", 0.30
    if score >= 6:
        return "适度做T", 0.20
    if score >= 5:
        return "保守做T", 0.15
    return "禁止做T", 0.0


def _profile_lookup(config: AppConfig) -> Dict[str, dict]:
    profiles = read_latest_csv(config.data.output_dir, "stock_profiles_*.csv")
    if profiles.empty or "symbol" not in profiles.columns:
        return {}
    profiles["symbol"] = profiles["symbol"].map(normalize_symbol)
    return {str(row["symbol"]): row for row in profiles.fillna("").to_dict("records")}


def _ma(hist: pd.DataFrame, window: int) -> float:
    if hist.empty:
        return 0.0
    return float(hist["close"].tail(window).mean())


def build_execution_plan_for_item(
    item: WatchItem,
    config: AppConfig,
    profile_row: Optional[dict] = None,
    market_return: float = 0.0,
    breadth_score: float = 0.0,
    breadth_flags: Optional[List[str]] = None,
    corp_action_flags: Optional[List[str]] = None,
) -> ExecutionPlan:
    daily = load_daily(item.symbol, config.data.daily_dir)
    minute = load_minute(item.symbol, config.data.minute_dir)
    signal_date = minute["date"].max()
    daily_snapshot = compute_daily_snapshot(daily, before_date=signal_date)
    intraday = compute_intraday_snapshot(
        minute,
        daily_snapshot,
        decision_time=config.signals.decision_time,
        signal_date=signal_date,
    )
    hist = daily[daily["date"] < signal_date].copy()
    ma5 = _ma(hist, 5)
    ma20 = _ma(hist, 20)
    atr = daily_snapshot.atr_pct_14
    avg_amount = daily_snapshot.avg_amount_20
    high_gap_rate = 0.0
    if profile_row:
        high_gap_rate = float(profile_row.get("high_gap_pullback_rate") or 0.0)

    if breadth_score > 0:
        market_score = breadth_score
    else:
        market_score = 1.2
        if market_return >= 0.008:
            market_score = 2.5
        elif market_return >= 0:
            market_score = 2.0
        elif market_return >= -0.008:
            market_score = 1.1
        else:
            market_score = 0.4

    volatility_score = _score_by_range(atr, 0.005, 0.015, 2.5)
    activity_score = _score_by_range(avg_amount, 50_000_000, 500_000_000, 2.0)
    pullback_score = 0.5
    if high_gap_rate >= 0.7:
        pullback_score = 1.5
    elif high_gap_rate >= 0.55:
        pullback_score = 1.1
    elif high_gap_rate >= 0.4:
        pullback_score = 0.7
    liquidity_score = _score_by_range(avg_amount, 50_000_000, 500_000_000, 1.0)

    score = market_score + volatility_score + activity_score + pullback_score + liquidity_score
    risk_flags: List[str] = []

    if corp_action_flags:
        risk_flags.extend(corp_action_flags)
        score = min(score, 4.9)

    if breadth_flags:
        risk_flags.extend(breadth_flags[:2])

    if atr < 0.005:
        score = min(score, 4.9)
        risk_flags.append("ATR不足0.5%，日内空间可能覆盖不了成本")
    if avg_amount < 50_000_000:
        score = min(score, 4.9)
        risk_flags.append("20日均成交额低于5000万，滑点风险高")
    if market_return < -0.008:
        risk_flags.append("市场偏弱，正T补仓需降仓")
    if intraday.open_gap >= 0.02:
        risk_flags.append("高开超过2%，分批反T，防止卖飞")

    recommendation, ratio = _recommendation(score)
    if recommendation == "禁止做T":
        risk_flags.append("评分低于5分，系统建议今日禁T")

    primary_strategy = "时间节点观察"
    if intraday.open_gap >= 0.01:
        primary_strategy = "高开反T"
    elif intraday.vwap_distance >= 0.005:
        primary_strategy = "VWAP偏离反T"
    elif intraday.open_gap <= -0.008 and intraday.reclaimed_vwap:
        primary_strategy = "低开修复正T"

    sell_ref_1 = daily_snapshot.prev_close * 1.01
    sell_ref_2 = daily_snapshot.prev_close * (1 + atr * 0.6)
    buy_ref_vwap = intraday.vwap
    buy_ref_ma = max(ma5, ma20) * 0.999
    buy_ref_atr = daily_snapshot.prev_close * (1 - atr * 0.4)
    stop_buyback = sell_ref_1 * 1.015

    return ExecutionPlan(
        symbol=item.symbol,
        name=item.name,
        sector=item.sector,
        signal_date=str(signal_date),
        suitability_score=round(float(score), 2),
        recommendation=recommendation,
        trade_ratio=ratio,
        primary_strategy=primary_strategy,
        sell_ref_1=round(sell_ref_1, 3),
        sell_ref_2=round(sell_ref_2, 3),
        buy_ref_vwap=round(buy_ref_vwap, 3),
        buy_ref_ma=round(buy_ref_ma, 3),
        buy_ref_atr=round(buy_ref_atr, 3),
        stop_buyback=round(stop_buyback, 3),
        force_buyback_time="14:45",
        atr_pct_14=round(atr, 4),
        high_gap_pullback_rate=round(high_gap_rate, 4),
        avg_amount_20=round(avg_amount, 2),
        risk_flags="；".join(risk_flags) or "无",
    )


def build_execution_plans(config: AppConfig) -> pd.DataFrame:
    try:
        items = load_watchlist(config.data.watchlist_path)
    except Exception:
        return pd.DataFrame()
    profiles = _profile_lookup(config)
    index_daily = maybe_load_daily(config.market_index_symbol, config.data.index_daily_dir)
    market_return = estimate_market_return(index_daily)

    breadth_score = 0.0
    breadth_flags: Optional[List[str]] = None
    try:
        from .market_breadth import fetch_breadth_cached
        mb = fetch_breadth_cached()
        if mb is not None:
            breadth_score = mb.breadth_score
            breadth_flags = [
                f"市场广度: {mb.sentiment} (涨停{mb.limit_up_count}/跌停{mb.limit_down_count})"
            ]
    except Exception:
        pass

    symbols = [item.symbol for item in items]
    corp_actions_map = {}
    try:
        from ..data.corporate_actions import batch_check_stocks
        corp_actions_map = batch_check_stocks(symbols)
    except Exception:
        pass

    rows = []
    for item in items:
        try:
            plan = build_execution_plan_for_item(
                item,
                config,
                profile_row=profiles.get(item.symbol),
                market_return=market_return,
                breadth_score=breadth_score,
                breadth_flags=breadth_flags,
                corp_action_flags=corp_actions_map.get(item.symbol),
            )
            rows.append(plan.__dict__)
        except Exception as exc:
            rows.append(
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "sector": item.sector,
                    "signal_date": "",
                    "suitability_score": 0.0,
                    "recommendation": "缺数据",
                    "trade_ratio": 0.0,
                    "primary_strategy": "-",
                    "sell_ref_1": 0.0,
                    "sell_ref_2": 0.0,
                    "buy_ref_vwap": 0.0,
                    "buy_ref_ma": 0.0,
                    "buy_ref_atr": 0.0,
                    "stop_buyback": 0.0,
                    "force_buyback_time": "14:45",
                    "atr_pct_14": 0.0,
                    "high_gap_pullback_rate": 0.0,
                    "avg_amount_20": 0.0,
                    "risk_flags": str(exc),
                    "status": "缺数据",
                }
            )
    return pd.DataFrame(rows)

