# Output Templates

Use these templates flexibly. Keep conclusions conditional and grounded in supplied/visible data.

## Mode A: Quick Judgment

```text
结论：{stage}，{risk_posture}。

当前阶段：{stage}
核心矛盾：{main_conflict}
关键防守区：{defense_zone_or_missing}
修复压力区：{repair_zone_or_missing}
失效条件：{invalid_condition}

最重要三个观察点：
1. {observation_1}
2. {observation_2}
3. {observation_3}
```

## Mode B: Complete Analysis

```text
一、总判断
{one_sentence_conclusion}

二、核心指标表
| 项目 | 观察 | 判断 |
| --- | --- | --- |
| 阶段 | {stage} | {stage_judgment} |
| 均线 | {ma_observation} | {ma_judgment} |
| MACD | {macd_observation} | {macd_judgment} |
| OBV | {obv_observation} | {obv_judgment} |
| 筹码 | {chip_observation} | {chip_judgment} |
| 量价 | {volume_observation} | {volume_judgment} |

三、阶段判断
{stage_detail}

四、均线趋势
{ma_detail}

五、MACD动量
{macd_detail}

六、OBV资金
{obv_detail}

七、筹码分布
{chip_detail}

八、量价换手
{volume_detail}

九、两融/龙虎榜/公告
{event_detail_or_missing}

十、关键价格区间
- 核心防守区：{defense_zone}
- 修复压力区：{repair_zone}
- 趋势确认区：{confirm_zone}
- 强压力区：{pressure_zone}
- 失效条件：{invalid_condition}

十一、综合评分
{score_or_qualitative_rating}

十二、操作纪律
{discipline}

十三、一句话总结
{summary}
```

## Mode C: Position Risk

```text
一、持仓数据
成本价：{cost_price}
当前价：{current_price}
持股数：{shares}

二、浮亏计算
| 项目 | 结果 |
| --- | ---: |
| 总成本 | {total_cost} |
| 当前市值 | {market_value} |
| 浮亏金额 | {pnl} |
| 浮亏比例 | {pnl_pct} |
| 回本所需涨幅 | {breakeven_gain_pct} |

三、关键价位对应盈亏
| 价格 | 位置含义 | 对应盈亏 |
| ---: | --- | ---: |
| {level} | {meaning} | {pnl_at_level} |

四、纪律线
- 防守线：{defense_line}
- 修复线：{repair_line}
- 减压线：{decompression_line}
- 解套线：{breakeven_line}
- 失效线：{invalid_line}
```

## Mode D: Multi-stock Comparison

```text
| 股票 | 阶段 | 趋势 | MACD | OBV | 筹码 | 风险 |
| --- | --- | --- | --- | --- | --- | --- |
| {stock} | {stage} | {trend} | {macd} | {obv} | {chip} | {risk} |

最强票：{name_and_reason}
最危险票：{name_and_reason}
最适合观察票：{name_and_reason}
最不适合追高票：{name_and_reason}
```

## Tone

- Direct, structured, and risk-aware.
- Avoid sensational wording.
- Prefer `如果...则...` conditions over categorical calls.
