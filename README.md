# 固定股票池做T量化系统

这是一个面向 A 股固定股票池的做T助手。它不做实盘下单，只负责：

- 读取你的自选股、日线、分钟线；
- 计算日线和早盘量价因子；
- 判断今日更适合反T、正T还是不动；
- 输出观察价、目标价、风控价、建议仓位；
- 用历史分钟线回测模型胜率；
- 生成每只股票的“日内性格画像”；
- 生成 CSV 和 Markdown 报告。

## 快速开始

```bash
python3 -m tquant.cli init
python3 -m tquant.cli generate-sample
python3 -m tquant.cli profile
python3 -m tquant.cli analyze
python3 -m tquant.cli backtest
```

生成结果在 `output/` 目录。

## 可视化工作台

本地启动：

```bash
python3 -m tquant_web.app
```

然后打开：

```text
http://127.0.0.1:8000
```

Docker 启动：

```bash
docker compose up -d --build
```

公网部署时建议设置访问密码：

```bash
export TQUANT_PASSWORD='换成你的强密码'
export TQUANT_SECRET_KEY='换成一串随机字符'
docker compose up -d --build
```

VPS 部署见 `deploy/README.md`。

工作台按实际使用顺序组织：

1. 先看 `数据状态`，确认每只股票是否有日线和分钟线；
2. 再点 `一键全部执行` 生成画像、信号和回测；
3. 从股票代码点进详情页，核对分时、VWAP、日线、核心因子和原始K线；
4. 数据缺失时去 `数据` 页上传 CSV，或用 AkShare 拉取股票池数据。

吸收新版方案后，工作台新增：

- `今日执行计划`：0-10 分做T适宜度、策略类型、T仓比例；
- `参考价格`：卖出参考、VWAP买回、均线买回、ATR买回、止损买回、14:45兜底；
- `复盘`：记录每次做T的卖出价、买回价、费用、净收益、月度胜率；
- `硬风控`：T仓不超过30%、评分低于5禁止做T、卖飞止损、尾盘兜底。

## 使用真实股票池

编辑 `config/watchlist.csv`：

```csv
symbol,name,sector,base_position,avg_cost
600519,贵州茅台,白酒,100,1500
300750,宁德时代,电池,300,180
```

然后把数据放入：

- `data/daily/{symbol}.csv`
- `data/minute/{symbol}.csv`

CSV 格式见 `data/README.md`。

## AkShare 数据

如果本机已安装 AkShare，可以尝试：

```bash
python3 -m tquant.cli fetch-akshare --daily --minute --start-date 20230101
```

AkShare 免费数据接口偶尔会变，若抓取失败，优先用本地 CSV 跑通模型。

## 模型逻辑

反T判断：高开、冲高远离 VWAP、早盘量能活跃、日线位置偏高、市场不太强时，优先考虑先卖后买回。

正T判断：低开、回踩后收回 VWAP、不破前低、市场不弱时，优先考虑先买后卖出底仓。

个股画像：统计每只股票高开后的回落概率、低开后的反弹概率、平均日内振幅、反T/正T机会率，以及最容易出现机会的开盘缺口区间。

系统会把一次做T的最低毛空间设为：

```text
佣金双边 + 过户费双边 + 卖出印花税 + 双边滑点 + 安全边际
```

默认佣金是万0.4，目标空间约 0.22%。实战可以在 `config/settings.json` 里调高 `safety_margin`。

## 重要边界

本系统是量价结构观察工具，不构成投资建议。第一版重点是让数据流、信号、回测、报告闭环跑通；真正实盘前，需要用你的真实股票池和真实交易记录继续校准参数。
