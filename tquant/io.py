from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd


DAILY_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]
MINUTE_COLUMNS = ["datetime", "open", "high", "low", "close", "volume", "amount"]


@dataclass(frozen=True)
class WatchItem:
    symbol: str
    name: str = ""
    sector: str = ""
    base_position: int = 0
    avg_cost: float = 0.0


def normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().zfill(6)


def load_watchlist(path: Path) -> List[WatchItem]:
    if not path.exists():
        raise FileNotFoundError(f"Watchlist not found: {path}")
    df = pd.read_csv(path, dtype={"symbol": str})
    if "symbol" not in df.columns:
        raise ValueError("watchlist.csv must contain a symbol column")
    items: List[WatchItem] = []
    for row in df.to_dict("records"):
        items.append(
            WatchItem(
                symbol=normalize_symbol(row.get("symbol", "")),
                name=str(row.get("name", "") or ""),
                sector=str(row.get("sector", "") or ""),
                base_position=int(row.get("base_position", 0) or 0),
                avg_cost=float(row.get("avg_cost", 0.0) or 0.0),
            )
        )
    return items


def _read_csv(path: Path, required_columns: Iterable[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    df = pd.read_csv(path)
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    return df


def load_daily(symbol: str, daily_dir: Path) -> pd.DataFrame:
    symbol = normalize_symbol(symbol)
    df = _read_csv(daily_dir / f"{symbol}.csv", DAILY_COLUMNS)
    df = df.copy()
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"]).sort_values("date")


def load_minute(symbol: str, minute_dir: Path) -> pd.DataFrame:
    symbol = normalize_symbol(symbol)
    df = _read_csv(minute_dir / f"{symbol}.csv", MINUTE_COLUMNS)
    df = df.copy()
    df["symbol"] = symbol
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date
    df["time"] = df["datetime"].dt.strftime("%H:%M")
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"]).sort_values("datetime")


def maybe_load_daily(symbol: str, daily_dir: Path) -> Optional[pd.DataFrame]:
    try:
        return load_daily(symbol, daily_dir)
    except FileNotFoundError:
        return None


def save_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)

