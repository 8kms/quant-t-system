from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .data.akshare_provider import fetch_akshare_daily, fetch_akshare_minute
from .core.backtest import run_backtest_for_items
from .config import AppConfig, ensure_project_dirs, load_config
from .core.features import (
    compute_daily_snapshot,
    compute_intraday_snapshot,
    estimate_market_return,
)
from .io import load_daily, load_minute, load_watchlist, maybe_load_daily, normalize_symbol
from .core.profile import build_stock_profiles, render_profile_report
from .report import write_backtest_outputs, write_signal_outputs
from .sample_data import generate_sample_dataset
from .core.signals import TSignal, TSignalEngine
from .workflow import (
    run_analyze as workflow_run_analyze,
    run_backtest as workflow_run_backtest,
    run_optimize as workflow_run_optimize,
    run_profile as workflow_run_profile,
)


def _parse_date(value: Optional[str]):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def cmd_init(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    ensure_project_dirs(config)
    settings = Path(args.config)
    if not settings.exists():
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(
            """{
  "market_index_symbol": "000001",
  "data": {
    "daily_dir": "data/daily",
    "minute_dir": "data/minute",
    "index_daily_dir": "data/index_daily",
    "output_dir": "output",
    "watchlist_path": "config/watchlist.csv",
    "journal_path": "data/trade_journal.csv",
    "market_breadth_dir": "data/market_breadth",
    "corp_actions_cache_dir": "data/corp_actions"
  },
  "costs": {
    "commission_rate": 0.00004,
    "stamp_tax_rate": 0.0005,
    "transfer_fee_rate": 0.00001,
    "slippage_rate": 0.0003,
    "safety_margin": 0.0015
  },
  "signals": {
    "decision_time": "09:35",
    "min_score_to_trade": 65,
    "strong_score": 80,
    "max_trade_ratio": 0.3,
    "normal_trade_ratio": 0.2,
    "small_trade_ratio": 0.1,
    "reverse_cancel_rate": 0.006,
    "positive_stop_rate": 0.006,
    "weak_market_threshold": -0.006,
    "strong_market_threshold": 0.006,
    "extreme_weak_market_threshold": -0.02,
    "extreme_strong_market_threshold": 0.02
  },
  "market": {
    "breadth_weight": 0.30,
    "extreme_limit_up": 80,
    "weak_limit_up": 15,
    "extreme_limit_down": 30,
    "breadth_lookback_days": 5
  }
}
""",
            encoding="utf-8",
        )
    if not config.data.watchlist_path.exists():
        config.data.watchlist_path.write_text(
            "symbol,name,sector,base_position,avg_cost\n",
            encoding="utf-8",
        )
    print(f"Initialized project at {Path.cwd()}")


def cmd_generate_sample(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    ensure_project_dirs(config)
    symbols = [normalize_symbol(sym) for sym in args.symbols.split(",")]
    generate_sample_dataset(
        symbols,
        config.data.daily_dir,
        config.data.minute_dir,
        config.data.index_daily_dir,
        config.data.watchlist_path,
    )
    print(f"Generated sample data for {', '.join(symbols)}")


def _load_maps(config: AppConfig, items) -> tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
    daily_map: Dict[str, pd.DataFrame] = {}
    minute_map: Dict[str, pd.DataFrame] = {}
    for item in items:
        daily_map[item.symbol] = load_daily(item.symbol, config.data.daily_dir)
        minute_map[item.symbol] = load_minute(item.symbol, config.data.minute_dir)
    return daily_map, minute_map


def cmd_analyze(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    csv_path, md_path = workflow_run_analyze(config, as_of=_parse_date(args.as_of))
    print(f"Wrote signals: {csv_path}")
    print(f"Wrote report: {md_path}")


def cmd_backtest(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    paths = workflow_run_backtest(config, start=_parse_date(args.start), end=_parse_date(args.end))
    for path in paths:
        print(f"Wrote {path}")


def cmd_profile(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    csv_path, md_path = workflow_run_profile(config)
    print(f"Wrote profile: {csv_path}")
    print(f"Wrote report: {md_path}")


def cmd_fetch_akshare(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    items = load_watchlist(config.data.watchlist_path)
    symbols = [item.symbol for item in items]
    if args.daily:
        fetch_akshare_daily(symbols, config.data.daily_dir, args.start_date, args.end_date)
    if args.minute:
        fetch_akshare_minute(symbols, config.data.minute_dir, period=args.period)
    print("AkShare fetch finished")


def cmd_fetch_market_breadth(args: argparse.Namespace) -> None:
    from .data.market_breadth import fetch_market_breadth

    print("Fetching market breadth data...")
    mb = fetch_market_breadth()
    if mb is None:
        print("Failed to fetch market breadth (API unavailable or non-trading day).")
        return
    print(f"Date: {mb.date}")
    print(f"Limit-up: {mb.limit_up_count}")
    print(f"Limit-down: {mb.limit_down_count}")
    print(f"Advance/Decline: {mb.advance_count}/{mb.decline_count} (total {mb.total_count})")
    print(f"Breadth Score: {mb.breadth_score:.2f}/3.0")
    print(f"Sentiment: {mb.sentiment}")


def cmd_check_corp_actions(args: argparse.Namespace) -> None:
    from .data.corporate_actions import batch_check_stocks

    config = load_config(args.config)
    items = load_watchlist(config.data.watchlist_path)
    symbols = [item.symbol for item in items]
    print(f"Checking corporate actions for {len(symbols)} stocks...")
    results = batch_check_stocks(symbols)
    if not results:
        print("No corporate action risks found.")
        return
    for sym, flags in results.items():
        print(f"\n{sym}:")
        for flag in flags:
            print(f"  - {flag}")


def cmd_optimize(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print("Running parameter optimization...")
    report = workflow_run_optimize(config)
    print(report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fixed watchlist A-share intraday T assistant")
    parser.add_argument("--config", default="config/settings.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create config and directories")
    p_init.set_defaults(func=cmd_init)

    p_sample = sub.add_parser("generate-sample", help="generate deterministic sample data")
    p_sample.add_argument("--symbols", default="000001,600519,300750")
    p_sample.set_defaults(func=cmd_generate_sample)

    p_analyze = sub.add_parser("analyze", help="generate today's T signals")
    p_analyze.add_argument("--as-of", help="YYYY-MM-DD minute date to analyze")
    p_analyze.set_defaults(func=cmd_analyze)

    p_backtest = sub.add_parser("backtest", help="run historical intraday T backtest")
    p_backtest.add_argument("--start", help="YYYY-MM-DD")
    p_backtest.add_argument("--end", help="YYYY-MM-DD")
    p_backtest.set_defaults(func=cmd_backtest)

    p_profile = sub.add_parser("profile", help="build per-stock intraday T personality profiles")
    p_profile.set_defaults(func=cmd_profile)

    p_fetch = sub.add_parser("fetch-akshare", help="fetch watchlist data from AkShare")
    p_fetch.add_argument("--daily", action="store_true")
    p_fetch.add_argument("--minute", action="store_true")
    p_fetch.add_argument("--start-date", default="20230101")
    p_fetch.add_argument("--end-date", default=datetime.now().strftime("%Y%m%d"))
    p_fetch.add_argument("--period", default="1")
    p_fetch.set_defaults(func=cmd_fetch_akshare)

    p_breadth = sub.add_parser("fetch-market-breadth", help="fetch market breadth data")
    p_breadth.set_defaults(func=cmd_fetch_market_breadth)

    p_corp = sub.add_parser("check-corp-actions", help="check corporate actions for watchlist")
    p_corp.set_defaults(func=cmd_check_corp_actions)

    p_opt = sub.add_parser("optimize", help="run parameter optimization from journal")
    p_opt.set_defaults(func=cmd_optimize)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
