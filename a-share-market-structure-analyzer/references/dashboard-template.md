# Dashboard Template

Use when the user asks for `做成图`, `生成仪表盘`, `分析卡片`, `报告图`, or `截图类似图片`.

## Required Visual Modules

1. Top risk banner: stock name/code, stage, risk level, one-sentence conclusion.
2. Core metric cards: current price, average cost, 70% zone, 90% zone, profit ratio, score.
3. MA system card: MA5/10/20/30/60 and trend interpretation.
4. MACD momentum card: cross, bar color, bar direction, zero-axis.
5. OBV funds card: confirmation/divergence/acceptance.
6. Chip structure card: concentration, chip peak, price-zone location.
7. Key price horizontal axis: defense, repair, confirmation, strong pressure, invalidation.
8. Score bar: total score and rating.
9. Operation discipline card: observe, reduce pressure, defend, invalidate.

## Layout Guidance

- Use a dense dashboard/report layout rather than a marketing page.
- Keep cards compact with clear hierarchy.
- Use color semantically:
  - Red/orange: risk, invalidation, pressure.
  - Green: repair, confirmation, positive acceptance.
  - Blue/gray: neutral observation.
- Do not put long paragraphs inside the image. Use short labels and concise status text.
- Include a small note: `结构诊断，不构成收益承诺`.

## Suggested Copy Blocks

Risk banner:

```text
{stock_name} {code}
阶段：{stage}
风险：{risk_level}
结论：{one_line_conclusion}
```

Price axis:

```text
失效 {invalid} | 防守 {defense} | 修复 {repair} | 确认 {confirm} | 强压 {pressure}
```

Discipline:

```text
站回{repair}: 初步修复
守住{defense}: 继续观察
跌破{invalid}: 风险升级
```

## Data Integrity

If a chart screenshot does not show a metric, render it as `未显示` rather than estimating it.
