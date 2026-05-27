#!/usr/bin/env python3
"""Calculate MA, MACD, and OBV from close/volume arrays."""

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


def _series(data: dict[str, Any], key: str) -> list[float]:
    values = data.get(key)
    if not isinstance(values, list) or not values:
        raise SystemExit(f"Field {key} must be a non-empty list of numbers.")
    result: list[float] = []
    for item in values:
        try:
            result.append(float(item))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"Field {key} contains a non-numeric value: {item!r}") from exc
    return result


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * alpha + result[-1] * (1 - alpha))
    return result


def macd(close: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, Any]:
    ema_fast = ema_series(close, fast)
    ema_slow = ema_series(close, slow)
    dif_series = [fast_value - slow_value for fast_value, slow_value in zip(ema_fast, ema_slow)]
    dea_series = ema_series(dif_series, signal)
    bar_series = [(dif - dea) * 2 for dif, dea in zip(dif_series, dea_series)]
    return {
        "dif_series": dif_series,
        "dea_series": dea_series,
        "macd_bar_series": bar_series,
        "dif": dif_series[-1],
        "dea": dea_series[-1],
        "macd_bar": bar_series[-1],
    }


def obv_series(close: list[float], volume: list[float]) -> list[float]:
    if len(close) != len(volume):
        raise SystemExit("Fields close and volume must have the same length.")
    result = [0.0]
    for idx in range(1, len(close)):
        if close[idx] > close[idx - 1]:
            result.append(result[-1] + volume[idx])
        elif close[idx] < close[idx - 1]:
            result.append(result[-1] - volume[idx])
        else:
            result.append(result[-1])
    return result


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _rounded(values: list[float]) -> list[float]:
    return [round(value, 4) for value in values]


def calculate(data: dict[str, Any], include_series: bool = False) -> dict[str, Any]:
    close = _series(data, "close")
    volume = _series(data, "volume")
    if len(close) != len(volume):
        raise SystemExit("Fields close and volume must have the same length.")

    macd_values = macd(close)
    obv_values = obv_series(close, volume)
    latest = {
        "ma5": _round_or_none(sma(close, 5)),
        "ma10": _round_or_none(sma(close, 10)),
        "ma20": _round_or_none(sma(close, 20)),
        "ma30": _round_or_none(sma(close, 30)),
        "ma60": _round_or_none(sma(close, 60)),
        "dif": round(macd_values["dif"], 4),
        "dea": round(macd_values["dea"], 4),
        "macd_bar": round(macd_values["macd_bar"], 4),
        "obv": round(obv_values[-1], 4),
    }

    result: dict[str, Any] = {
        "periods": len(close),
        "latest": latest,
        "signal": {
            "macd_bar_color": "red" if latest["macd_bar"] > 0 else "green" if latest["macd_bar"] < 0 else "flat",
            "dif_above_dea": latest["dif"] > latest["dea"],
            "dif_above_zero": latest["dif"] > 0,
        },
    }
    if include_series:
        result["series"] = {
            "dif": _rounded(macd_values["dif_series"]),
            "dea": _rounded(macd_values["dea_series"]),
            "macd_bar": _rounded(macd_values["macd_bar_series"]),
            "obv": _rounded(obv_values),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate MA, MACD, and OBV from JSON close/volume arrays.")
    parser.add_argument("--input", "-i", help="JSON input file. Defaults to stdin.")
    parser.add_argument("--series", action="store_true", help="Include full MACD and OBV series.")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    args = parser.parse_args()

    result = calculate(_read_json(args.input), include_series=args.series)
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
