from __future__ import annotations

from typing import Dict, Iterable, List

import pandas as pd

from ..config import AppConfig
from .features import compute_daily_snapshot, compute_intraday_snapshot
from ..io import WatchItem


def _rate(values: List[bool]) -> float:
    if not values:
        return 0.0
    return round(float(sum(values) / len(values)), 4)


def _bucket_gap(gap: float) -> str:
    pct = gap * 100
    if pct >= 3:
        return "高开>3%"
    if pct >= 2:
        return "高开2%-3%"
    if pct >= 1:
        return "高开1%-2%"
    if pct >= 0.5:
        return "高开0.5%-1%"
    if pct <= -3:
        return "低开<-3%"
    if pct <= -2:
        return "低开2%-3%"
    if pct <= -1:
        return "低开1%-2%"
    if pct <= -0.5:
        return "低开0.5%-1%"
    return "平开"


def build_stock_profiles(
    items: Iterable[WatchItem],
    daily_map: Dict[str, pd.DataFrame],
    minute_map: Dict[str, pd.DataFrame],
    config: AppConfig,
) -> pd.DataFrame:
    rows = []
    edge = config.costs.practical_edge_rate
    for item in items:
        daily = daily_map[item.symbol]
        minute = minute_map[item.symbol]
        dates = sorted(minute["date"].unique())
        high_gap_cases: List[bool] = []
        low_gap_cases: List[bool] = []
        reverse_cases: List[bool] = []
        positive_cases: List[bool] = []
        amplitudes: List[float] = []
        gap_rows = []

        for signal_date in dates:
            try:
                daily_snapshot = compute_daily_snapshot(daily, before_date=signal_date)
                intra = compute_intraday_snapshot(
                    minute,
                    daily_snapshot,
                    decision_time=config.signals.decision_time,
                    signal_date=signal_date,
                )
            except ValueError:
                continue

            day = minute[minute["date"] == signal_date]
            after = day[day["time"] > intra.decision_time]
            if after.empty:
                continue
            future_low = float(after["low"].min())
            future_high = float(after["high"].max())
            reverse_ok = future_low <= intra.current_price * (1 - edge)
            positive_ok = future_high >= intra.current_price * (1 + edge)
            amplitude = (
                float(day["high"].max()) - float(day["low"].min())
            ) / daily_snapshot.prev_close
            amplitudes.append(amplitude)
            gap_rows.append(
                {
                    "bucket": _bucket_gap(intra.open_gap),
                    "reverse_ok": reverse_ok,
                    "positive_ok": positive_ok,
                }
            )
            if intra.open_gap >= 0.006:
                high_gap_cases.append(reverse_ok)
            if intra.open_gap <= -0.006:
                low_gap_cases.append(positive_ok)
            reverse_cases.append(reverse_ok)
            positive_cases.append(positive_ok)

        gap_df = pd.DataFrame(gap_rows)
        best_bucket = ""
        if not gap_df.empty:
            summary = (
                gap_df.groupby("bucket")
                .agg(
                    cases=("bucket", "size"),
                    reverse_rate=("reverse_ok", "mean"),
                    positive_rate=("positive_ok", "mean"),
                )
                .reset_index()
            )
            summary = summary[summary["cases"] >= 2]
            if not summary.empty:
                summary["best_rate"] = summary[["reverse_rate", "positive_rate"]].max(axis=1)
                best_bucket = str(
                    summary.sort_values("best_rate", ascending=False).iloc[0]["bucket"]
                )

        reverse_rate = _rate(reverse_cases)
        positive_rate = _rate(positive_cases)
        rows.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "sector": item.sector,
                "sample_days": len(reverse_cases),
                "avg_intraday_amplitude": round(
                    float(pd.Series(amplitudes).mean()) if amplitudes else 0.0, 4
                ),
                "high_gap_pullback_rate": _rate(high_gap_cases),
                "low_gap_rebound_rate": _rate(low_gap_cases),
                "reverse_t_opportunity_rate": reverse_rate,
                "positive_t_opportunity_rate": positive_rate,
                "preferred_t_style": "反T优先" if reverse_rate >= positive_rate else "正T优先",
                "best_gap_bucket": best_bucket,
            }
        )
    return pd.DataFrame(rows)


def render_profile_report(profile: pd.DataFrame) -> str:
    lines = [
        "# 固定股票池个股画像",
        "",
        "说明：画像用于识别每只股票自己的日内波动性格，不构成投资建议。",
        "",
    ]
    if profile.empty:
        lines.append("无数据。")
        return "\n".join(lines)
    lines.append(profile.to_markdown(index=False))
    lines.append("")
    lines.append("解读重点：")
    lines.append("- high_gap_pullback_rate 越高，越适合高开后做反T观察。")
    lines.append("- low_gap_rebound_rate 越高，越适合低开后做正T观察。")
    lines.append("- avg_intraday_amplitude 低于目标做T空间时，不适合频繁做T。")
    lines.append("")
    return "\n".join(lines)

