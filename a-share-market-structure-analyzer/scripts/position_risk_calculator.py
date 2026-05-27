#!/usr/bin/env python3
"""Calculate A-share position risk from JSON input."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _read_json(path: str | None) -> dict[str, Any]:
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raw = sys.stdin.read().strip()
    if not raw:
        raise SystemExit("No JSON input provided. Use --input path.json or pipe JSON to stdin.")
    return json.loads(raw)


def _number(data: dict[str, Any], key: str, *, positive: bool = False) -> float:
    if key not in data:
        raise SystemExit(f"Missing required field: {key}")
    try:
        value = float(data[key])
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Field {key} must be numeric.") from exc
    if positive and value <= 0:
        raise SystemExit(f"Field {key} must be greater than 0.")
    return value


def _levels(data: dict[str, Any], key: str) -> list[float]:
    values = data.get(key, [])
    if values is None:
        return []
    if not isinstance(values, list):
        raise SystemExit(f"Field {key} must be a list of numbers.")
    result: list[float] = []
    for item in values:
        try:
            result.append(float(item))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"Field {key} contains a non-numeric value: {item!r}") from exc
    return sorted(result)


def _round(value: float) -> float:
    return round(value, 4)


def _money(value: float) -> float:
    return round(value, 2)


def _pct(value: float) -> float:
    return round(value, 2)


def _line_range(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {"lower": round(min(values), 2), "upper": round(max(values), 2)}


def calculate(data: dict[str, Any]) -> dict[str, Any]:
    cost_price = _number(data, "cost_price", positive=True)
    current_price = _number(data, "current_price", positive=True)
    shares = _number(data, "shares", positive=True)
    support_levels = _levels(data, "support_levels")
    resistance_levels = _levels(data, "resistance_levels")

    total_cost = cost_price * shares
    market_value = current_price * shares
    unrealized_pnl = market_value - total_cost
    pnl_pct = (current_price / cost_price - 1) * 100
    breakeven_gain_pct = (cost_price / current_price - 1) * 100

    level_rows = []
    seen_prices: set[float] = set()
    for label, values in (("support", support_levels), ("resistance", resistance_levels)):
        for price in values:
            rounded_price = round(price, 4)
            if rounded_price in seen_prices:
                continue
            seen_prices.add(rounded_price)
            value_at_level = price * shares
            pnl_at_level = value_at_level - total_cost
            level_rows.append(
                {
                    "price": round(price, 4),
                    "type": label,
                    "market_value": _money(value_at_level),
                    "pnl": _money(pnl_at_level),
                    "pnl_pct_vs_cost": _pct((price / cost_price - 1) * 100),
                    "gain_pct_from_current": _pct((price / current_price - 1) * 100),
                }
            )
    level_rows.sort(key=lambda row: row["price"])

    next_resistances = [p for p in resistance_levels if p > current_price]
    resistance_above_cost = [p for p in resistance_levels if p >= cost_price]
    discipline_lines = {
        "defense_line": _line_range(support_levels),
        "repair_line": round(next_resistances[0], 2) if next_resistances else None,
        "decompression_line": round(next_resistances[0], 2) if next_resistances else None,
        "breakeven_line": round(cost_price, 4),
        "unlock_line": round(resistance_above_cost[0], 2) if resistance_above_cost else round(cost_price, 4),
        "invalid_line": round(min(support_levels), 2) if support_levels else None,
    }

    return {
        "inputs": {
            "cost_price": _round(cost_price),
            "current_price": _round(current_price),
            "shares": _round(shares),
            "support_levels": [round(v, 4) for v in support_levels],
            "resistance_levels": [round(v, 4) for v in resistance_levels],
        },
        "summary": {
            "total_cost": _money(total_cost),
            "market_value": _money(market_value),
            "unrealized_pnl": _money(unrealized_pnl),
            "unrealized_pnl_pct": _pct(pnl_pct),
            "breakeven_required_gain_pct": _pct(breakeven_gain_pct),
        },
        "level_pnl": level_rows,
        "discipline_lines": discipline_lines,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate A-share position risk from JSON.")
    parser.add_argument("--input", "-i", help="JSON input file. Defaults to stdin.")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    args = parser.parse_args()

    result = calculate(_read_json(args.input))
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
