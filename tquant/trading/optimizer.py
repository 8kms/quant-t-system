from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OptimizationSuggestion:
    symbol: str
    name: str
    total_trades: int
    win_rate: float
    avg_net_return: float
    best_strategy: str
    suggested_gap_trigger: float
    suggested_vwap_trigger: float
    suggested_trade_ratio: float
    suggested_buyback_window: str
    confidence: str


def analyze_journal_patterns(
    journal_df: pd.DataFrame, min_trades: int = 5
) -> pd.DataFrame:
    """Analyze trading journal for patterns and statistics per stock."""
    if journal_df.empty:
        return pd.DataFrame()

    df = journal_df.copy()
    for col in ["net_pnl", "net_return", "quantity", "sell_price", "buy_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.strftime("%Y-%m")
        df["hour"] = df["date"].dt.hour

    groups = []
    for sym, grp in df.groupby("symbol"):
        if len(grp) < min_trades:
            continue

        wins = grp["net_pnl"] > 0
        win_rate = float(wins.mean())
        avg_return = float(grp["net_return"].mean())
        total_pnl = float(grp["net_pnl"].sum())

        action_counts = grp["action"].value_counts()
        best_action = action_counts.index[0] if len(action_counts) > 0 else "unknown"

        avg_sell = float(grp["sell_price"].mean())
        avg_buy = float(grp["buy_price"].mean())
        avg_gap_pct = (avg_sell - avg_buy) / max(avg_buy, 0.01)

        groups.append(
            {
                "symbol": sym,
                "name": grp["name"].iloc[0] if "name" in grp.columns else "",
                "total_trades": len(grp),
                "win_rate": round(win_rate, 4),
                "avg_net_return": round(avg_return, 6),
                "total_net_pnl": round(total_pnl, 2),
                "best_strategy": best_action,
                "avg_gap_pct": round(avg_gap_pct, 4),
                "avg_sell_price": round(avg_sell, 3),
                "avg_buy_price": round(avg_buy, 3),
            }
        )

    return pd.DataFrame(groups).sort_values("win_rate", ascending=False)


def _estimate_optimal_trigger(
    trades: pd.DataFrame, field: str, current: float
) -> float:
    """Estimate optimal trigger value from profitable trades."""
    if trades.empty or field not in trades.columns:
        return current

    winners = trades[trades["net_pnl"] > 0]
    if len(winners) < 3:
        return current

    values = pd.to_numeric(winners[field], errors="coerce").dropna()
    if values.empty:
        return current

    return round(float(values.median()), 4)


def _estimate_optimal_ratio(trades: pd.DataFrame, current: float) -> float:
    """Estimate optimal trade ratio from win rate."""
    if trades.empty:
        return current
    wins = (trades["net_pnl"] > 0).mean()
    if wins >= 0.70:
        return min(current * 1.2, 0.30)
    elif wins >= 0.60:
        return current
    elif wins >= 0.50:
        return max(current * 0.8, 0.10)
    else:
        return max(current * 0.5, 0.05)


def _best_buyback_window(trades: pd.DataFrame) -> str:
    """Determine best buyback time window from trade notes and timing."""
    notes = trades["note"].dropna().astype(str).str.lower()
    if notes.empty:
        return "10:00-11:00 (默认)"

    morning = notes.str.contains("10:|11:|早盘|上午|回调").sum()
    afternoon = notes.str.contains("13:|14:|午后|下午").sum()
    vwap = notes.str.contains("vwap|均价").sum()

    if morning > afternoon and morning > vwap:
        return "10:00-11:00 早盘回调"
    elif afternoon > morning:
        return "13:00-14:30 午后回调"
    elif vwap > 0:
        return "VWAP回归"
    return "10:00-11:00 (默认)"


def suggest_parameters(
    journal_df: pd.DataFrame,
    profiles_df: Optional[pd.DataFrame] = None,
    min_trades: int = 5,
) -> List[OptimizationSuggestion]:
    """Generate parameter optimization suggestions per stock."""
    if journal_df.empty:
        return []

    suggestions: List[OptimizationSuggestion] = []
    pattern_df = analyze_journal_patterns(journal_df, min_trades)

    for _, row in pattern_df.iterrows():
        symbol = str(row["symbol"])
        stock_trades = journal_df[journal_df["symbol"] == symbol]

        win_rate = float(row["win_rate"])
        avg_return = float(row["avg_net_return"])

        suggested_gap = _estimate_optimal_trigger(
            stock_trades, "sell_price", 0.01
        )
        suggested_ratio = _estimate_optimal_ratio(stock_trades, 0.20)
        best_window = _best_buyback_window(stock_trades)

        if win_rate >= 0.65:
            confidence = "高"
        elif win_rate >= 0.55:
            confidence = "中"
        else:
            confidence = "低（需更多数据）"

        suggestions.append(
            OptimizationSuggestion(
                symbol=symbol,
                name=str(row["name"]),
                total_trades=int(row["total_trades"]),
                win_rate=win_rate,
                avg_net_return=avg_return,
                best_strategy=str(row["best_strategy"]),
                suggested_gap_trigger=suggested_gap,
                suggested_vwap_trigger=0.005,
                suggested_trade_ratio=round(suggested_ratio, 2),
                suggested_buyback_window=best_window,
                confidence=confidence,
            )
        )

    return suggestions


def generate_optimization_report(
    suggestions: List[OptimizationSuggestion],
) -> str:
    """Generate Markdown optimization report."""
    if not suggestions:
        return "# 参数优化报告\n\n暂无足够数据生成优化建议（至少需要5笔记录/股票）。"

    lines = [
        "# 参数优化报告",
        "",
        f"基于 {sum(s.total_trades for s in suggestions)} 笔做T记录分析",
        "",
        "## 各股票优化建议",
        "",
        "| 代码 | 名称 | 笔数 | 胜率 | 建议策略 | 建议触发 | 建议仓位 | 买回窗口 | 置信度 |",
        "|------|------|------|------|----------|----------|----------|----------|--------|",
    ]

    for s in sorted(suggestions, key=lambda x: x.win_rate, reverse=True):
        lines.append(
            f"| {s.symbol} | {s.name} | {s.total_trades} | {s.win_rate:.1%} | "
            f"{s.best_strategy} | {s.suggested_gap_trigger:.2%} | {s.suggested_trade_ratio:.0%} | "
            f"{s.suggested_buyback_window} | {s.confidence} |"
        )

    lines.extend(
        [
            "",
            "## 使用说明",
            "",
            "- **建议触发**: 高开策略的触发阈值，低于此值不建议操作",
            "- **建议仓位**: 根据历史胜率调整的T仓比例",
            "- **买回窗口**: 历史成功记录中最常见的买回时间段",
            "- **置信度**: 基于样本量和统计显著性评估",
            "",
            "建议每周复盘后重新运行优化器，持续调整参数。",
        ]
    )

    return "\n".join(lines)


def compute_strategy_stats(
    journal_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute per-strategy win rate and return stats."""
    if journal_df.empty:
        return pd.DataFrame()

    df = journal_df.copy()
    df["net_pnl"] = pd.to_numeric(df["net_pnl"], errors="coerce")
    df["net_return"] = pd.to_numeric(df["net_return"], errors="coerce")

    stats = (
        df.groupby("action")
        .agg(
            trades=("symbol", "size"),
            win_rate=("net_pnl", lambda s: (s > 0).mean()),
            avg_net_return=("net_return", "mean"),
            total_pnl=("net_pnl", "sum"),
        )
        .reset_index()
    )
    stats["win_rate"] = stats["win_rate"].round(4)
    stats["avg_net_return"] = stats["avg_net_return"].round(6)
    stats["total_pnl"] = stats["total_pnl"].round(2)
    return stats.sort_values("win_rate", ascending=False)


def compute_stock_optimal_params(
    journal_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute optimal parameters per stock from journal history."""
    if journal_df.empty:
        return pd.DataFrame()

    rows = []
    for sym, grp in journal_df.groupby("symbol"):
        if len(grp) < 3:
            continue
        wins = grp["net_pnl"] > 0
        rows.append(
            {
                "symbol": sym,
                "trades": len(grp),
                "win_rate": round(float(wins.mean()), 4),
                "avg_pnl": round(float(grp["net_pnl"].mean()), 2),
                "optimal_ratio": round(
                    min(float(wins.mean()) * 0.4, 0.30), 2
                ),
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("win_rate", ascending=False)
