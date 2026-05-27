#!/usr/bin/env python3
"""Calculate weighted A-share structure score."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


WEIGHTS = {
    "trend": 18,
    "macd": 12,
    "obv": 15,
    "chip": 20,
    "volume": 12,
    "funding": 8,
    "sector": 8,
    "position": 7,
}

ALIASES = {
    "trend_structure": "trend",
    "macd_momentum": "macd",
    "obv_funds": "obv",
    "chip_structure": "chip",
    "volume_turnover": "volume",
    "funding_sentiment": "funding",
    "sector_linkage": "sector",
    "position_risk": "position",
}


def _read_json(path: str | None) -> dict[str, Any]:
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raw = sys.stdin.read().strip()
    if not raw:
        raise SystemExit("No JSON input provided. Use --input path.json or pipe JSON to stdin.")
    return json.loads(raw)


def rating_for(score: float) -> tuple[str, str]:
    if score >= 80:
        return "强势进攻", "低"
    if score >= 65:
        return "偏强观察", "中低"
    if score >= 50:
        return "中性博弈", "中"
    if score >= 35:
        return "偏弱防守", "中高"
    return "破位风险", "高"


def _extract_scores(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("scores"), dict):
        return data["scores"]
    if isinstance(data.get("modules"), dict):
        return data["modules"]
    return data


def calculate(data: dict[str, Any]) -> dict[str, Any]:
    raw_scores = _extract_scores(data)
    normalized: dict[str, float | None] = {key: None for key in WEIGHTS}
    warnings: list[str] = []

    for key, value in raw_scores.items():
        canonical = ALIASES.get(key, key)
        if canonical not in WEIGHTS:
            continue
        if value is None or value == "暂缺":
            normalized[canonical] = None
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            warnings.append(f"{canonical} ignored because it is not numeric: {value!r}")
            normalized[canonical] = None
            continue
        weight = WEIGHTS[canonical]
        clamped = min(max(numeric, 0), weight)
        if clamped != numeric:
            warnings.append(f"{canonical} clamped from {numeric} to {clamped}.")
        normalized[canonical] = clamped

    missing = [key for key, value in normalized.items() if value is None]
    total = round(sum(value for value in normalized.values() if value is not None), 2)
    rating, risk_level = rating_for(total)

    return {
        "total_score": total,
        "rating": rating,
        "risk_level": risk_level,
        "weights": WEIGHTS,
        "breakdown": normalized,
        "missing_modules": missing,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate weighted A-share structure score from JSON.")
    parser.add_argument("--input", "-i", help="JSON input file. Defaults to stdin.")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    args = parser.parse_args()

    result = calculate(_read_json(args.input))
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
