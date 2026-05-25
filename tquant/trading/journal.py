from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from ..config import AppConfig
from ..io import normalize_symbol, save_dataframe


JOURNAL_COLUMNS = [
    "date",
    "symbol",
    "name",
    "action",
    "quantity",
    "sell_price",
    "buy_price",
    "gross_pnl",
    "fees",
    "net_pnl",
    "net_return",
    "note",
]


def read_journal(config: AppConfig) -> pd.DataFrame:
    path = config.data.journal_path
    if not path.exists():
        return pd.DataFrame(columns=JOURNAL_COLUMNS)
    return pd.read_csv(path, dtype={"symbol": str}).fillna("")


def append_trade(config: AppConfig, row: Dict[str, object]) -> Dict[str, object]:
    symbol = normalize_symbol(str(row.get("symbol", "")))
    quantity = int(float(row.get("quantity") or 0))
    sell_price = float(row.get("sell_price") or 0)
    buy_price = float(row.get("buy_price") or 0)
    if quantity <= 0:
        raise ValueError("数量必须大于0")
    if sell_price <= 0 or buy_price <= 0:
        raise ValueError("卖出价和买回价必须大于0")

    sell_amount = sell_price * quantity
    buy_amount = buy_price * quantity
    gross_pnl = sell_amount - buy_amount
    fees = (
        (sell_amount + buy_amount)
        * (config.costs.commission_rate + config.costs.transfer_fee_rate)
        + sell_amount * config.costs.stamp_tax_rate
    )
    net_pnl = gross_pnl - fees
    base = buy_amount if buy_amount else 1.0
    record = {
        "date": row.get("date") or datetime.now().strftime("%Y-%m-%d"),
        "symbol": symbol,
        "name": row.get("name", ""),
        "action": row.get("action", "反T"),
        "quantity": quantity,
        "sell_price": round(sell_price, 3),
        "buy_price": round(buy_price, 3),
        "gross_pnl": round(gross_pnl, 2),
        "fees": round(fees, 2),
        "net_pnl": round(net_pnl, 2),
        "net_return": round(net_pnl / base, 6),
        "note": row.get("note", ""),
    }
    df = read_journal(config)
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    save_dataframe(df[JOURNAL_COLUMNS], config.data.journal_path)
    return record


def journal_summary(df: pd.DataFrame) -> Dict[str, object]:
    if df.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_net_return": 0.0,
            "by_symbol": pd.DataFrame(),
            "by_month": pd.DataFrame(),
        }
    work = df.copy()
    work["net_pnl"] = pd.to_numeric(work["net_pnl"], errors="coerce").fillna(0)
    work["net_return"] = pd.to_numeric(work["net_return"], errors="coerce").fillna(0)
    work["month"] = pd.to_datetime(work["date"]).dt.strftime("%Y-%m")
    by_symbol = (
        work.groupby(["symbol", "name"], dropna=False)
        .agg(trades=("symbol", "size"), win_rate=("net_pnl", lambda s: (s > 0).mean()), net_pnl=("net_pnl", "sum"), avg_return=("net_return", "mean"))
        .reset_index()
    )
    by_month = (
        work.groupby("month", dropna=False)
        .agg(trades=("symbol", "size"), win_rate=("net_pnl", lambda s: (s > 0).mean()), net_pnl=("net_pnl", "sum"), avg_return=("net_return", "mean"))
        .reset_index()
    )
    return {
        "trades": int(len(work)),
        "win_rate": round(float((work["net_pnl"] > 0).mean()), 4),
        "net_pnl": round(float(work["net_pnl"].sum()), 2),
        "avg_net_return": round(float(work["net_return"].mean()), 6),
        "by_symbol": by_symbol,
        "by_month": by_month,
    }

