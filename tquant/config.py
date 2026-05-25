from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CostConfig:
    """Trading cost assumptions for one stock round trip."""

    commission_rate: float = 0.00004
    stamp_tax_rate: float = 0.0005
    transfer_fee_rate: float = 0.00001
    slippage_rate: float = 0.0003
    safety_margin: float = 0.0015

    @property
    def round_trip_rate(self) -> float:
        return (
            self.commission_rate * 2
            + self.transfer_fee_rate * 2
            + self.stamp_tax_rate
        )

    @property
    def practical_edge_rate(self) -> float:
        return self.round_trip_rate + self.slippage_rate * 2 + self.safety_margin


@dataclass(frozen=True)
class SignalConfig:
    decision_time: str = "09:35"
    min_score_to_trade: float = 65.0
    strong_score: float = 80.0
    max_trade_ratio: float = 0.30
    normal_trade_ratio: float = 0.20
    small_trade_ratio: float = 0.10
    reverse_cancel_rate: float = 0.006
    positive_stop_rate: float = 0.006
    weak_market_threshold: float = -0.006
    strong_market_threshold: float = 0.006
    extreme_weak_market_threshold: float = -0.02
    extreme_strong_market_threshold: float = 0.02


@dataclass(frozen=True)
class MarketConfig:
    breadth_weight: float = 0.30
    extreme_limit_up: int = 80
    weak_limit_up: int = 15
    extreme_limit_down: int = 30
    breadth_lookback_days: int = 5


@dataclass(frozen=True)
class DataConfig:
    daily_dir: Path = Path("data/daily")
    minute_dir: Path = Path("data/minute")
    index_daily_dir: Path = Path("data/index_daily")
    output_dir: Path = Path("output")
    watchlist_path: Path = Path("config/watchlist.csv")
    journal_path: Path = Path("data/trade_journal.csv")
    market_breadth_dir: Path = Path("data/market_breadth")
    corp_actions_cache_dir: Path = Path("data/corp_actions")


@dataclass(frozen=True)
class AppConfig:
    data: DataConfig = field(default_factory=DataConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    market_index_symbol: str = "000001"


def _coerce_path(value: Optional[str], default: Path) -> Path:
    if value is None:
        return default
    return Path(value)


def load_config(path: str = "config/settings.json") -> AppConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return AppConfig()

    raw: Dict[str, Any] = json.loads(cfg_path.read_text(encoding="utf-8"))
    data_raw = raw.get("data", {})
    cost_raw = raw.get("costs", {})
    signal_raw = raw.get("signals", {})
    market_raw = raw.get("market", {})

    data = DataConfig(
        daily_dir=_coerce_path(data_raw.get("daily_dir"), DataConfig.daily_dir),
        minute_dir=_coerce_path(data_raw.get("minute_dir"), DataConfig.minute_dir),
        index_daily_dir=_coerce_path(
            data_raw.get("index_daily_dir"), DataConfig.index_daily_dir
        ),
        output_dir=_coerce_path(data_raw.get("output_dir"), DataConfig.output_dir),
        watchlist_path=_coerce_path(
            data_raw.get("watchlist_path"), DataConfig.watchlist_path
        ),
        journal_path=_coerce_path(
            data_raw.get("journal_path"), DataConfig.journal_path
        ),
        market_breadth_dir=_coerce_path(
            data_raw.get("market_breadth_dir"), DataConfig.market_breadth_dir
        ),
        corp_actions_cache_dir=_coerce_path(
            data_raw.get("corp_actions_cache_dir"), DataConfig.corp_actions_cache_dir
        ),
    )
    costs = CostConfig(**{**CostConfig().__dict__, **cost_raw})
    signals = SignalConfig(**{**SignalConfig().__dict__, **signal_raw})
    market = MarketConfig(**{**MarketConfig().__dict__, **market_raw})
    return AppConfig(
        data=data,
        costs=costs,
        signals=signals,
        market=market,
        market_index_symbol=raw.get("market_index_symbol", "000001"),
    )


def ensure_project_dirs(config: AppConfig) -> None:
    paths: List[Path] = [
        config.data.daily_dir,
        config.data.minute_dir,
        config.data.index_daily_dir,
        config.data.output_dir,
        config.data.watchlist_path.parent,
        config.data.journal_path.parent,
        config.data.market_breadth_dir,
        config.data.corp_actions_cache_dir,
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
