# 指数轮动量化系统 - 当前技术架构

**版本**: v2.1  
**最后更新**: 2026-03-25  
**说明**: 本文件是当前唯一的正式技术架构说明

## 一、正式运行链路

### 正式代码

- `src/data_fetcher_baostock.py`
- `src/dashboard_builder.py`
- `src/scoring_baostock.py`
- `src/market_regime.py`
- `src/strategy_summary.py`
- `src/strategy_baostock.py`
- `src/portfolio.py`
- `src/backtest_utils.py`

### 正式脚本

- `scripts/daily_run_baostock.py`
- `scripts/backtest_baostock.py`
- `scripts/generate_data.py`

### 展示层

- `web/`
- `scripts/report_server.py`

### 运行产物

- `web/public/`
- `reports/`
- `logs/`

### 历史实现

- `src/legacy/`

## 二、架构分层

### 1. 数据层

文件：`src/data_fetcher_baostock.py`

职责：

- 获取 ETF 历史行情
- 获取北向资金
- 获取 ETF 份额
- 管理本地 Parquet 缓存

### 2. 策略层

文件：`src/strategy_baostock.py`

职责：

- 加载配置
- 调用数据抓取
- 调用评分引擎
- 生成调仓信号
- 驱动模拟账户

### 3. 评分层

文件：

- `src/scoring_baostock.py`
- `src/market_regime.py`

职责：

- 计算主线因子分数
- 根据市场状态调整权重
- 输出综合评分与排名

### 4. 回测层

文件：`scripts/backtest_baostock.py`

职责：

- 获取历史数据
- 按统一规则模拟调仓
- 输出净值、收益、回撤、夏普等结果

### 5. 数据发布层

文件：

- `scripts/generate_data.py`
- `web/public/`

职责：

- 生成前端消费的 JSON
- 将运行产物与 React 看板解耦

### 6. 展示层

文件：

- `web/`
- `scripts/report_server.py`

职责：

- 前端展示策略状态
- 提供报告资源列表和静态访问

## 三、目录约定

```text
quant-rotation/
├── config/
├── src/
│   └── legacy/
├── scripts/
├── web/
├── requirements/
├── data/
├── backtest_results/
├── reports/
└── logs/
```

## 四、运行命令

```bash
python scripts/daily_run_baostock.py
python scripts/backtest_baostock.py
python scripts/generate_data.py

cd web
npm run build
npm run preview
```

## 五、技术口径

- 当前默认环境为 Python 3.9+
- 默认依赖以 `requirements/base.txt` 为准
- 正式活跃池为 19 只指数；`000921.CSI -> 512340` 已标记为失效代理并移出正式池
- 如遇旧文档与本文件冲突，以本文件为准
