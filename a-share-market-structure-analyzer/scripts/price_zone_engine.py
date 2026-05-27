#!/usr/bin/env python3
"""Generate A-share key price zones from MA and chip inputs."""

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


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in data:
            return _num(data[key])
    ma = data.get("ma")
    if isinstance(ma, dict):
        for key in keys:
            if key in ma:
                return _num(ma[key])
    chip = data.get("chip")
    if isinstance(chip, dict):
        for key in keys:
            if key in chip:
                return _num(chip[key])
    return None


def _zone_pair(data: dict[str, Any], *keys: str) -> tuple[float | None, float | None]:
    for key in keys:
        value = data.get(key)
        if value is None and isinstance(data.get("chip"), dict):
            value = data["chip"].get(key)
        if isinstance(value, list) and len(value) >= 2:
            low = _num(value[0])
            high = _num(value[1])
            if low is None or high is None:
                continue
            return (min(low, high), max(low, high))
        if isinstance(value, dict):
            low = _num(value.get("lower", value.get("low")))
            high = _num(value.get("upper", value.get("high")))
            if low is None or high is None:
                continue
            return (min(low, high), max(low, high))
    return (None, None)


def _zone(name: str, components: dict[str, float | None]) -> dict[str, Any]:
    present = {key: round(value, 4) for key, value in components.items() if value is not None}
    missing = [key for key, value in components.items() if value is None]
    if not present:
        return {"name": name, "lower": None, "upper": None, "components": present, "missing_components": missing}
    values = list(present.values())
    return {
        "name": name,
        "lower": round(min(values), 2),
        "upper": round(max(values), 2),
        "components": present,
        "missing_components": missing,
        "quality": "zone" if len(values) >= 2 else "single_observation",
    }


def _obv_down(data: dict[str, Any]) -> bool:
    state = str(data.get("obv_state", data.get("obv", ""))).lower()
    return any(token in state for token in ("down", "turn_down", "下拐", "下行", "回落"))


def calculate(data: dict[str, Any]) -> dict[str, Any]:
    cost70_low, cost70_high = _zone_pair(data, "cost70", "cost_70", "cost70_zone", "cost_70_zone")
    cost90_low, cost90_high = _zone_pair(data, "cost90", "cost_90", "cost90_zone", "cost_90_zone")
    ma5 = _get(data, "ma5")
    ma10 = _get(data, "ma10")
    ma20 = _get(data, "ma20")
    ma30 = _get(data, "ma30")
    avg_cost = _get(data, "avg_cost", "average_cost")
    recent_low = _get(data, "recent_low", "near_low")
    previous_high = _get(data, "previous_high", "prev_high", "front_high")
    platform_level = _get(data, "platform_level", "key_platform")

    zones = {
        "defense_zone": _zone(
            "核心防守区",
            {
                "70_cost_lower": cost70_low,
                "ma20": ma20,
                "recent_low": recent_low,
            },
        ),
        "repair_zone": _zone(
            "修复压力区",
            {
                "average_cost": avg_cost,
                "ma5": ma5,
                "ma10": ma10,
            },
        ),
        "confirmation_zone": _zone(
            "趋势确认区",
            {
                "ma20": ma20,
                "ma30": ma30,
                "platform_level": platform_level,
            },
        ),
        "strong_pressure_zone": _zone(
            "强压力区",
            {
                "70_cost_upper": cost70_high,
                "90_cost_upper": cost90_high,
                "previous_high": previous_high,
            },
        ),
    }

    if cost70_low is not None and _obv_down(data):
        invalid_condition = f"跌破{cost70_low:.2f}且OBV明显下拐，视为风险升级"
    elif cost70_low is not None:
        invalid_condition = f"有效跌破{cost70_low:.2f}，核心筹码区失守"
    elif ma20 is not None and ma30 is not None:
        invalid_condition = f"跌破{min(ma20, ma30):.2f}-{max(ma20, ma30):.2f}且站不回，趋势降级"
    elif ma20 is not None:
        invalid_condition = f"跌破MA20 {ma20:.2f}且站不回，趋势降级"
    else:
        invalid_condition = "关键防守区失守且OBV同步下拐，风险升级"

    missing_notes = []
    if cost70_low is None or cost70_high is None:
        missing_notes.append("70%成本区缺失，核心防守区和强压力区需要筹码截图确认")
    if cost90_high is None:
        missing_notes.append("90%成本区缺失，强压力区不完整")

    return {
        "zones": zones,
        "invalid_condition": invalid_condition,
        "missing_notes": missing_notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate A-share key price zones from JSON.")
    parser.add_argument("--input", "-i", help="JSON input file. Defaults to stdin.")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    args = parser.parse_args()

    result = calculate(_read_json(args.input))
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
