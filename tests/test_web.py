import tempfile
import unittest
from pathlib import Path

from tquant.config import AppConfig, DataConfig
from tquant.report import write_backtest_outputs, write_signal_outputs
from tquant.sample_data import generate_sample_dataset
from tquant.signals import TSignal
from tquant.workflow import run_backtest, run_profile
from tquant_web.app import create_app


class WebAppTest(unittest.TestCase):
    def test_dashboard_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "settings.json"
            config_path.write_text(
                """{
  "data": {
    "daily_dir": "%s",
    "minute_dir": "%s",
    "index_daily_dir": "%s",
    "output_dir": "%s",
    "watchlist_path": "%s"
  }
}
"""
                % (
                    root / "daily",
                    root / "minute",
                    root / "index",
                    root / "output",
                    root / "watchlist.csv",
                ),
                encoding="utf-8",
            )
            data = DataConfig(
                daily_dir=root / "daily",
                minute_dir=root / "minute",
                index_daily_dir=root / "index",
                output_dir=root / "output",
                watchlist_path=root / "watchlist.csv",
            )
            generate_sample_dataset(["600519"], data.daily_dir, data.minute_dir, data.index_daily_dir, data.watchlist_path)
            app = create_app(str(config_path))
            client = app.test_client()
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("做T决策台".encode("utf-8"), response.data)
            self.assertIn("数据状态".encode("utf-8"), response.data)
            self.assertIn("今日执行计划".encode("utf-8"), response.data)
            detail = client.get("/stock/600519")
            self.assertEqual(detail.status_code, 200)
            self.assertIn("核心因子".encode("utf-8"), detail.data)
            self.assertIn("今日执行计划".encode("utf-8"), detail.data)
            journal = client.get("/journal")
            self.assertEqual(journal.status_code, 200)
            self.assertIn("做T记录与复盘".encode("utf-8"), journal.data)


if __name__ == "__main__":
    unittest.main()
