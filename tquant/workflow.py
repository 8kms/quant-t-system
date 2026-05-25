from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .core.backtest import BacktestResult, run_backtest_for_items
from .config import AppConfig, ensure_project_dirs
from .core.features import compute_daily_snapshot, compute_intraday_snapshot, estimate_market_return
from .io import (
    WatchItem,
    load_daily,
    load_minute,
    load_watchlist,
    maybe_load_daily,
    normalize_symbol,
    save_dataframe,
)
from .trading.journal import read_journal
from .trading.optimizer import generate_optimization_report, suggest_parameters
from .core.profile import build_stock_profiles, render_profile_report
from .report import write_backtest_outputs, write_signal_outputs
from .sample_data import generate_sample_dataset
from .core.signals import TSignal, TSignalEngine


def load_watch_items(config: AppConfig) -> List[WatchItem]:
    ensure_project_dirs(config)
    return load_watchlist(config.data.watchlist_path)


def load_data_maps(
    items: Iterable[WatchItem], config: AppConfig
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
    daily_map: Dict[str, pd.DataFrame] = {}
    minute_map: Dict[str, pd.DataFrame] = {}
    for item in items:
        daily_map[item.symbol] = load_daily(item.symbol, config.data.daily_dir)
        minute_map[item.symbol] = load_minute(item.symbol, config.data.minute_dir)
    return daily_map, minute_map


def load_available_data(
    items: Iterable[WatchItem], config: AppConfig
) -> Tuple[List[WatchItem], Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
    available_items: List[WatchItem] = []
    daily_map: Dict[str, pd.DataFrame] = {}
    minute_map: Dict[str, pd.DataFrame] = {}
    for item in items:
        try:
            daily = load_daily(item.symbol, config.data.daily_dir)
            minute = load_minute(item.symbol, config.data.minute_dir)
        except Exception:
            continue
        if len(daily) < 25 or minute.empty:
            continue
        available_items.append(item)
        daily_map[item.symbol] = daily
        minute_map[item.symbol] = minute
    return available_items, daily_map, minute_map


def run_analyze(config: AppConfig, as_of=None) -> Tuple[Path, Path]:
    items = load_watch_items(config)
    engine = TSignalEngine(config.costs, config.signals)
    index_daily = maybe_load_daily(config.market_index_symbol, config.data.index_daily_dir)
    market_return = estimate_market_return(index_daily, as_of=as_of)

    breadth_score = 0.0
    breadth_flags: List[str] = []
    try:
        from .data.market_breadth import fetch_breadth_cached
        mb = fetch_breadth_cached()
        if mb is not None:
            breadth_score = mb.breadth_score
            breadth_flags = [
                f"市场广度: {mb.sentiment} (涨停{mb.limit_up_count}/跌停{mb.limit_down_count})"
            ]
    except Exception:
        pass

    signals: List[TSignal] = []
    for item in items:
        try:
            daily = load_daily(item.symbol, config.data.daily_dir)
            minute = load_minute(item.symbol, config.data.minute_dir)
            signal_date = as_of or minute["date"].max()
            daily_snapshot = compute_daily_snapshot(daily, before_date=signal_date)
            intra_snapshot = compute_intraday_snapshot(
                minute,
                daily_snapshot,
                decision_time=config.signals.decision_time,
                signal_date=signal_date,
            )
            signals.append(
                engine.generate(
                    item,
                    daily_snapshot,
                    intra_snapshot,
                    market_return,
                    breadth_score=breadth_score,
                    breadth_flags=breadth_flags,
                )
            )
        except Exception:
            continue
    return write_signal_outputs(signals, config.data.output_dir)


def run_profile(config: AppConfig) -> Tuple[Path, Path]:
    items = load_watch_items(config)
    available_items, daily_map, minute_map = load_available_data(items, config)
    profile = build_stock_profiles(available_items, daily_map, minute_map, config)
    config.data.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = config.data.output_dir / f"stock_profiles_{stamp}.csv"
    md_path = config.data.output_dir / f"stock_profiles_{stamp}.md"
    profile.to_csv(csv_path, index=False)
    md_path.write_text(render_profile_report(profile), encoding="utf-8")
    return csv_path, md_path


def run_backtest(config: AppConfig, start=None, end=None) -> List[Path]:
    items = load_watch_items(config)
    available_items, daily_map, minute_map = load_available_data(items, config)
    result: BacktestResult = run_backtest_for_items(
        available_items,
        daily_map,
        minute_map,
        config,
        start=start,
        end=end,
    )
    return write_backtest_outputs(result, config.data.output_dir)


def generate_samples(config: AppConfig, symbols: Iterable[str]) -> None:
    ensure_project_dirs(config)
    generate_sample_dataset(
        [normalize_symbol(symbol) for symbol in symbols],
        config.data.daily_dir,
        config.data.minute_dir,
        config.data.index_daily_dir,
        config.data.watchlist_path,
    )


def latest_file(output_dir: Path, pattern: str) -> Optional[Path]:
    files = sorted(output_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def read_latest_csv(output_dir: Path, pattern: str) -> pd.DataFrame:
    path = latest_file(output_dir, pattern)
    if path is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype={"symbol": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].map(normalize_symbol)
    return df


def build_data_status(config: AppConfig) -> pd.DataFrame:
    rows = []
    try:
        items = load_watch_items(config)
    except Exception:
        items = []
    for item in items:
        daily_path = config.data.daily_dir / f"{item.symbol}.csv"
        minute_path = config.data.minute_dir / f"{item.symbol}.csv"
        row = {
            "symbol": item.symbol,
            "name": item.name,
            "sector": item.sector,
            "daily_rows": 0,
            "minute_rows": 0,
            "latest_daily": "",
            "latest_minute": "",
            "status": "缺数据",
            "message": "",
        }
        messages = []
        if daily_path.exists():
            try:
                daily = load_daily(item.symbol, config.data.daily_dir)
                row["daily_rows"] = len(daily)
                row["latest_daily"] = str(daily["date"].max())
                if len(daily) < 25:
                    messages.append("日线少于25根")
            except Exception as exc:
                messages.append(f"日线错误: {exc}")
        else:
            messages.append("缺日线")

        if minute_path.exists():
            try:
                minute = load_minute(item.symbol, config.data.minute_dir)
                row["minute_rows"] = len(minute)
                row["latest_minute"] = str(minute["datetime"].max())
            except Exception as exc:
                messages.append(f"分钟线错误: {exc}")
        else:
            messages.append("缺分钟线")

        if not messages:
            row["status"] = "可用"
            row["message"] = "数据完整"
        else:
            row["message"] = "；".join(messages)
        rows.append(row)
    return pd.DataFrame(rows)


def save_watchlist_rows(config: AppConfig, rows: List[dict]) -> None:
    clean_rows = []
    for row in rows:
        symbol = normalize_symbol(row.get("symbol", ""))
        if not symbol.strip("0"):
            continue
        clean_rows.append(
            {
                "symbol": symbol,
                "name": row.get("name", ""),
                "sector": row.get("sector", ""),
                "base_position": int(float(row.get("base_position") or 0)),
                "avg_cost": float(row.get("avg_cost") or 0),
            }
        )
    df = pd.DataFrame(
        clean_rows,
        columns=["symbol", "name", "sector", "base_position", "avg_cost"],
    )
    save_dataframe(df, config.data.watchlist_path)


def run_optimize(config: AppConfig) -> str:
    journal_df = read_journal(config)
    if journal_df.empty:
        return "# 参数优化报告\n\n暂无做T记录。请先记录至少10笔做T操作后再运行优化。\n"

    suggestions = suggest_parameters(journal_df)
    report = generate_optimization_report(suggestions)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = config.data.output_dir / f"optimization_{stamp}.md"
    md_path.write_text(report, encoding="utf-8")

    suggestions_data = []
    for s in suggestions:
        suggestions_data.append(
            {
                "symbol": s.symbol,
                "name": s.name,
                "total_trades": s.total_trades,
                "win_rate": s.win_rate,
                "avg_net_return": s.avg_net_return,
                "best_strategy": s.best_strategy,
                "suggested_gap_trigger": s.suggested_gap_trigger,
                "suggested_trade_ratio": s.suggested_trade_ratio,
                "suggested_buyback_window": s.suggested_buyback_window,
                "confidence": s.confidence,
            }
        )
    if suggestions_data:
        csv_path = config.data.output_dir / f"optimization_{stamp}.csv"
        pd.DataFrame(suggestions_data).to_csv(csv_path, index=False)

    return report
