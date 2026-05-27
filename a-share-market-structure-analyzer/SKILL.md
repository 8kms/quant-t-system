---
name: a-share-market-structure-analyzer
description: Analyze Chinese A-share stocks from chart screenshots, stock codes, user-provided position data, margin financing, Dragon Tiger List, announcements, and sector information. Use for A-share technical analysis involving moving averages, MACD death crosses or green bars, OBV divergence, volume, turnover, chip distribution, chip concentration, profit/loss chip ratios, key support and resistance zones, position risk, scorecards, execution discipline, multi-stock comparison, and dashboard-style stock analysis reports.
---

# A股盘面结构诊断

Use this Skill to produce structured A-share market diagnostics. The goal is not to predict涨跌 with certainty; it is to identify stage, trend integrity,资金承接,筹码压力,持仓风险,关键价位, and conditional execution discipline.

## Hard Rules

- Treat every conclusion as conditional and probabilistic.
- Never use: `铁底`, `必涨`, `必跌`, `主力一定护盘`, `机构一定低吸`, `融资买入就是利好`, `死叉必跌`, `金叉必涨`.
- Prefer: `核心防守区`, `关键观察位`, `修复确认区`, `压力释放区`, `风险升级`, `资金承接`, `高位分歧`, `派发风险`.
- Always classify the stage before interpreting indicators.
- Never conclude from one indicator alone. Cross-check trend, MACD, OBV, volume/turnover, chips, funding events, sector context, and position risk where available.
- Screenshot-visible data takes priority. If a value is not visible or not provided, say `该项截图未显示` or `当前输入未提供`; do not invent it.
- OBV can support `资金仍有承接` or `存在低吸/防守可能`; it does not prove institutional accumulation.
- Financing data is leverage behavior, not automatically bullish. Rising leverage helps on breakouts and hurts on breakdowns.
- For latest market data, announcements, margin data, Dragon Tiger List, or sector changes, verify with current sources when tools are available and cite them. If unavailable, analyze only supplied data.
- This is analytical risk guidance, not personalized investment advice.

## Workflow

1. Identify input type: screenshot, stock code/name, position data, funding event, announcement, Dragon Tiger List, sector info, or multi-stock comparison.
2. Extract visible/provided metrics and explicitly mark missing fields.
3. Classify the current stage before interpreting any signal.
4. Analyze MA trend, MACD momentum, OBV funds, volume/turnover, chip distribution, funding events, announcement context, and sector linkage.
5. Generate key price zones: defense, repair pressure, trend confirmation, strong pressure, invalidation.
6. Score the structure using the weighted model when enough data exists.
7. If position data exists, compute cost, market value, floating P/L, breakeven gain, level-by-level P/L, and discipline lines.
8. Select the output mode and finish with actionable observation conditions.
9. Generate a dashboard/report image only when requested by words such as `做成图`, `生成仪表盘`, `分析卡片`, `报告图`, or `截图类似图片`.

## Input Router

- **Quick question** (`这个怎么看`, `危险吗`, `死叉严不严重`): use Quick Judgment output.
- **Screenshot or full chart request**: use Complete Analysis output and load chip/indicator rules as needed.
- **Cost, shares, or position amount present**: use Position Risk output and run `scripts/position_risk_calculator.py` when numeric inputs are complete.
- **Multiple stocks**: use Multi-stock Comparison output.
- **Dashboard/report image requested**: use Dashboard output guidance.
- **Stock code/name without data**: retrieve current data if possible; otherwise ask for chart/chip screenshots for unavailable fields such as 70%/90% chip zones.

## References

- Load [workflow.md](references/workflow.md) for the complete end-to-end procedure.
- Load [stage-classification.md](references/stage-classification.md) before interpreting indicator meaning.
- Load [indicator-rules.md](references/indicator-rules.md) for MA, MACD, OBV, volume, and turnover rules.
- Load [chip-rules.md](references/chip-rules.md) for chip distribution, concentration, cost-zone, and profit/loss chip logic.
- Load [price-zone-rules.md](references/price-zone-rules.md) to generate defense, repair, confirmation, pressure, and invalidation zones.
- Load [funding-event-rules.md](references/funding-event-rules.md) for margin financing, Dragon Tiger List, announcements, and sector context.
- Load [scoring-model.md](references/scoring-model.md) when producing a numerical score.
- Load [output-templates.md](references/output-templates.md) for quick, complete, position, and multi-stock formats.
- Load [dashboard-template.md](references/dashboard-template.md) when generating a visual report.
- Load [glossary.md](references/glossary.md) for consistent Chinese terms.

## Scripts

- `scripts/position_risk_calculator.py`: calculate holding cost, current value, floating P/L, breakeven gain, and level-by-level P/L from JSON.
- `scripts/indicator_calculator.py`: calculate MA5/10/20/30/60, MACD, and OBV from close/volume arrays.
- `scripts/score_engine.py`: calculate total score, rating, and risk level from weighted module scores.
- `scripts/price_zone_engine.py`: generate key price zones from MA, chip-cost zones, average cost, highs/lows, and OBV state.

Each script accepts JSON from `--input path.json` or stdin and emits JSON. Prefer scripts for deterministic calculations instead of doing arithmetic by hand.

## Output Discipline

- Start with a one-sentence conclusion that names stage and risk posture.
- Keep price zones numeric and conditional.
- Separate facts, inference, and missing data.
- For holders, include `防守线`, `修复线`, `减压线`, `解套线`, and `失效线`.
- End with the 3 most important observations or a single-line summary.
