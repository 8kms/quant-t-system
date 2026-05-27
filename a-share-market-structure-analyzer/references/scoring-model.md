# Scoring Model

Total score is 100.

| Module | Weight |
| --- | ---: |
| Trend structure | 18 |
| MACD momentum | 12 |
| OBV funds | 15 |
| Chip structure | 20 |
| Volume/turnover | 12 |
| Funding sentiment | 8 |
| Sector linkage | 8 |
| Position risk | 7 |

## Rating

| Score | Rating | Meaning |
| ---: | --- | --- |
| 80-100 | 强势进攻 | Trend healthy |
| 65-79 | 偏强观察 | Trend exists, wait for confirmation |
| 50-64 | 中性博弈 | Long/short disagreement |
| 35-49 | 偏弱防守 | Control risk |
| 0-34 | 破位风险 | Prioritize defense |

## Risk Level

- `低`: 80-100
- `中低`: 65-79
- `中`: 50-64
- `中高`: 35-49
- `高`: 0-34

## Scoring Guidance

- Score only modules with evidence. Avoid false precision when key data is missing.
- If a module is missing, either omit numerical score or show `暂缺`.
- If scoring despite missing data, explicitly say `因筹码/两融/板块数据缺失，评分偏保守`.
- Penalize high-position structures when MACD, OBV, volume, and chip break signals align.
- Reward repair only when price reclaim and OBV/MACD confirmation occur together.

## Module Anchors

- Trend: MA stack, price relative to MA20/MA30/MA60, platform break/reclaim.
- MACD: cross, bar direction, zero-axis, divergence.
- OBV: confirmation, divergence, support/collapse.
- Chips: average cost, 70%/90% zone, concentration, profit/trapped ratio, chip peak.
- Volume/turnover: expansion/shrinkage, long bearish candle, turnover stability.
- Funding: margin crowding/withdrawal, Dragon Tiger quality, announcement interpretation.
- Sector: sector trend, theme heat, relative strength.
- Position: cost distance, drawdown, breakeven difficulty, invalidation distance.
