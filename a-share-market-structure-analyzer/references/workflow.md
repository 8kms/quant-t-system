# Workflow

Use this sequence for complete A-share structure diagnosis.

## 1. Input Recognition

Classify all available inputs:

- Screenshot: chart, chip distribution, MACD, OBV, trading app, margin financing, Dragon Tiger List, announcement, or position.
- Text: stock name/code, cost, shares, current price, support/resistance, funding events, announcements, sector clues.
- Multi-stock: two or more names/codes or an explicit comparison request.
- Dashboard request: words such as `做成图`, `生成仪表盘`, `报告图`, `分析卡片`.

## 2. Data Extraction

Extract only visible or supplied data:

- Price: current price, recent high/low, previous high, platform level.
- Trend: MA5, MA10, MA20, MA30, MA60.
- MACD: DIF, DEA, bar color/size, cross, zero-axis position, divergence.
- OBV: direction, new high/new low, divergence, support during decline.
- Volume/turnover: shrink/expand, high turnover, long bearish candle, volume-price mismatch.
- Chips: average cost, 70% cost zone, 90% cost zone, concentration70/90, profit ratio, trapped ratio, chip peak.
- Events: margin balance/buying, short balance, Dragon Tiger seats, announcement type, sector strength.
- Position: cost price, current price, shares, planned support/resistance levels.

If data is missing, say so. Do not fill chip cost zones from imagination.

## 3. Stage First

Load `stage-classification.md` and classify the stage before interpreting MACD, OBV, or chips. The same MACD death cross can mean a mild strong-trend cool-down or a breakdown continuation depending on stage.

## 4. Indicator Diagnosis

Load `indicator-rules.md` for:

- MA stack and price position.
- MACD cross, histogram, zero-axis, and divergence.
- OBV confirmation/divergence.
- Volume and turnover behavior.

## 5. Chip Structure

Load `chip-rules.md` for:

- Price position relative to average cost, 70% zone, and 90% zone.
- Concentration interpretation by stage.
- Profit/trapped chip pressure.
- Chip peak movement.

## 6. Event Overlay

Load `funding-event-rules.md` when margin financing, Dragon Tiger List, announcements, or sector information exists. Always combine event interpretation with price position and chip/trend structure.

## 7. Key Price Zones

Load `price-zone-rules.md` and generate:

- Core defense zone.
- Repair pressure zone.
- Trend confirmation zone.
- Strong pressure zone.
- Invalidation condition.

Use the script `scripts/price_zone_engine.py` when numeric inputs are complete.

## 8. Score

Load `scoring-model.md` when enough modules have data. If key modules are missing, provide a qualitative score range instead of false precision.

## 9. Position Risk

If cost/current/shares are provided, run `scripts/position_risk_calculator.py` and integrate:

- Total cost.
- Current market value.
- Floating profit/loss.
- Breakeven required gain.
- P/L at key levels.
- Defense, repair, decompression, breakeven, invalidation lines.

## 10. Output Mode

Use `output-templates.md`:

- Quick Judgment for short user questions.
- Complete Analysis for screenshots/full asks.
- Position Risk for holdings.
- Multi-stock Comparison for ranking.

Use `dashboard-template.md` only for visual report requests.
