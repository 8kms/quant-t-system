import tempfile
import unittest
from pathlib import Path

from tquant.backtest import run_backtest_for_items
from tquant.config import AppConfig, DataConfig
from tquant.features import compute_daily_snapshot, compute_intraday_snapshot
from tquant.io import load_daily, load_minute, load_watchlist
from tquant.sample_data import generate_sample_dataset
from tquant.signals import TSignalEngine


class PipelineTest(unittest.TestCase):
    def test_sample_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = DataConfig(
                daily_dir=root / "daily",
                minute_dir=root / "minute",
                index_daily_dir=root / "index",
                output_dir=root / "output",
                watchlist_path=root / "watchlist.csv",
            )
            config = AppConfig(data=data)
            generate_sample_dataset(["000001", "600519"], data.daily_dir, data.minute_dir, data.index_daily_dir, data.watchlist_path)
            items = load_watchlist(data.watchlist_path)
            daily = load_daily(items[0].symbol, data.daily_dir)
            minute = load_minute(items[0].symbol, data.minute_dir)
            signal_date = minute["date"].max()
            daily_snapshot = compute_daily_snapshot(daily, before_date=signal_date)
            intraday_snapshot = compute_intraday_snapshot(minute, daily_snapshot, signal_date=signal_date)
            signal = TSignalEngine(config.costs, config.signals).generate(items[0], daily_snapshot, intraday_snapshot)
            self.assertIn(signal.action, {"reverse_t", "positive_t", "hold"})

            result = run_backtest_for_items(
                items,
                {item.symbol: load_daily(item.symbol, data.daily_dir) for item in items},
                {item.symbol: load_minute(item.symbol, data.minute_dir) for item in items},
                config,
            )
            self.assertFalse(result.trades.empty)


if __name__ == "__main__":
    unittest.main()

