# Price Zone Rules

Generate five price zones whenever enough numeric data exists. Use ranges, not a single magic price.

## Core Defense Zone

Logic:

```text
70% cost lower edge + MA20 + recent low
```

Interpretation:

- This is the first area where trend/chip defense should appear.
- If price enters this zone with shrinking volume and stable OBV, it may be healthy testing.
- If price breaks this zone with OBV down and volume expansion, risk upgrades.

## Repair Pressure Zone

Logic:

```text
average cost + MA5 + MA10
```

Interpretation:

- Reclaiming this zone is initial repair.
- Failing here means weak rebound or pressure-release rebound.

## Trend Confirmation Zone

Logic:

```text
MA20 + MA30 + key platform level
```

Interpretation:

- Reclaiming/holding this zone improves trend confirmation.
- Losing this zone downgrades from attack/repair to defense.

## Strong Pressure Zone

Logic:

```text
70% cost upper edge + 90% cost upper edge + previous high
```

Interpretation:

- This is the area of strong supply/profit pressure.
- Breakout needs volume, OBV confirmation, and no obvious MACD divergence.

## Invalidation Zone

Logic:

```text
valid break below 70% lower edge
or MA20/MA30 loss
or OBV turning down together
```

For high-position structures, use:

```text
跌破70%成本下沿且OBV明显下拐，视为高位派发风险升级。
```

For weak structures, use:

```text
跌破90%成本下沿且反弹无量，视为筹码结构破坏。
```

## Zone Quality Rules

- Use two decimals for A-share prices when data is numeric.
- If multiple components are available, the range is `[min(component values), max(component values)]`.
- If only one component exists, call it a `关键观察位` rather than a full zone.
- If chip data is missing, generate MA/platform zones and explicitly say chip-zone generation needs screenshot confirmation.
