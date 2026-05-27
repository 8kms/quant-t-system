# Position Risk Example

User input:

```text
成本48.688，当前44.00，持股23042股。支撑43.20、44.40，压力46.35、47.84、50.10。
```

Run:

```bash
python3 scripts/position_risk_calculator.py <<'JSON'
{
  "cost_price": 48.688,
  "current_price": 44.0,
  "shares": 23042,
  "support_levels": [43.2, 44.4],
  "resistance_levels": [46.35, 47.84, 50.1]
}
JSON
```

Expected use in answer:

```text
结论：当前持仓处于浮亏防守状态，核心是先看43.20—44.40防守区能否稳住，再看46.35/47.84是否形成减压。

防守线：43.20—44.40
修复线：46.35
减压线：46.35
解套线：48.688
失效线：43.20
```
