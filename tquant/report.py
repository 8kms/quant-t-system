from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from .config import AppConfig
from .core.signals import TSignal


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def signal_to_dict(signal: TSignal) -> dict:
    return {
        "date": signal.signal_date,
        "symbol": signal.symbol,
        "name": signal.name,
        "sector": signal.sector,
        "action": signal.action,
        "action_cn": signal.action_cn,
        "score": signal.score,
        "confidence": signal.confidence,
        "trade_ratio": signal.trade_ratio,
        "observe_price": signal.observe_price,
        "target_price": signal.target_price,
        "cancel_price": signal.cancel_price,
        "expected_edge_pct": signal.expected_edge_pct,
        "reasons": " | ".join(signal.reasons),
        "warnings": " | ".join(signal.warnings),
    }


def write_signal_outputs(signals: Iterable[TSignal], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [signal_to_dict(signal) for signal in signals]
    columns = [
        "date",
        "symbol",
        "name",
        "sector",
        "action",
        "action_cn",
        "score",
        "confidence",
        "trade_ratio",
        "observe_price",
        "target_price",
        "cancel_price",
        "expected_edge_pct",
        "reasons",
        "warnings",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df = df.sort_values(["action", "score"], ascending=[True, False])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"signals_{stamp}.csv"
    md_path = output_dir / f"daily_report_{stamp}.md"
    df.to_csv(csv_path, index=False)
    md_path.write_text(render_daily_report(rows), encoding="utf-8")
    return csv_path, md_path


def render_daily_report(rows: List[dict]) -> str:
    active = [row for row in rows if row["action"] != "hold"]
    holds = [row for row in rows if row["action"] == "hold"]
    active = sorted(active, key=lambda row: row["score"], reverse=True)

    lines = [
        "# 固定股票池做T日报",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "说明：本报告只做量价结构观察和风险提示，不构成投资建议。",
        "",
        "## 今日优先观察",
        "",
    ]
    if not active:
        lines.append("今日没有达到阈值的做T机会。")
    else:
        lines.append("| 排名 | 代码 | 名称 | 动作 | 分数 | 仓位 | 观察价 | 目标价 | 放弃/风控价 |")
        lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|")
        for idx, row in enumerate(active, 1):
            lines.append(
                "| {idx} | {symbol} | {name} | {action_cn} | {score:.2f} | {ratio} | "
                "{observe:.3f} | {target:.3f} | {cancel:.3f} |".format(
                    idx=idx,
                    symbol=row["symbol"],
                    name=row["name"],
                    action_cn=row["action_cn"],
                    score=row["score"],
                    ratio=_pct(row["trade_ratio"]),
                    observe=row["observe_price"],
                    target=row["target_price"],
                    cancel=row["cancel_price"],
                )
            )
        lines.append("")
        lines.append("## 原因链条")
        lines.append("")
        for row in active:
            lines.append(f"### {row['symbol']} {row['name']}")
            lines.append(f"- 动作：{row['action_cn']}")
            lines.append(f"- 评分：{row['score']:.2f}，置信度：{row['confidence']}")
            lines.append(f"- 主要原因：{row['reasons'] or '无'}")
            lines.append(f"- 风险提示：{row['warnings'] or '无'}")
            lines.append("")

    lines.append("## 不做T观察池")
    lines.append("")
    if not holds:
        lines.append("无。")
    else:
        for row in sorted(holds, key=lambda item: item["score"], reverse=True):
            lines.append(
                f"- {row['symbol']} {row['name']}：{row['score']:.2f} 分，{row['warnings'] or row['reasons']}"
            )
    lines.append("")
    return "\n".join(lines)


def write_backtest_outputs(result, output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: List[Path] = []
    tables = {
        "backtest_trades": result.trades,
        "backtest_summary": result.summary,
        "backtest_by_symbol": result.by_symbol,
        "backtest_by_action": result.by_action,
        "backtest_by_year": result.by_year,
    }
    for name, df in tables.items():
        path = output_dir / f"{name}_{stamp}.csv"
        df.to_csv(path, index=False)
        paths.append(path)
    md_path = output_dir / f"backtest_report_{stamp}.md"
    md_path.write_text(render_backtest_report(result), encoding="utf-8")
    paths.append(md_path)
    return paths


def _table_or_empty(df: pd.DataFrame) -> str:
    if df.empty:
        return "无数据\n"
    return df.to_markdown(index=False)


def render_backtest_report(result) -> str:
    lines = [
        "# 做T模型回测报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "说明：回测使用分钟线模拟触发目标价/风控价；同一根K线同时触发时按保守顺序处理。",
        "",
        "## 总览",
        "",
        _table_or_empty(result.summary),
        "",
        "## 按动作",
        "",
        _table_or_empty(result.by_action),
        "",
        "## 按股票",
        "",
        _table_or_empty(result.by_symbol),
        "",
        "## 按年份",
        "",
        _table_or_empty(result.by_year),
        "",
    ]
    return "\n".join(lines)
