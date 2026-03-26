# 指数轮动量化系统 - 项目总览

## 当前状态

- 正式运行链路已收敛
- 旧实现已迁移到 `legacy/`
- 主线已可完成评分、回测、前端生成和页面展示

## 正式运行链路

### 核心代码

- `src/data_fetcher_baostock.py`
- `src/scoring_baostock.py`
- `src/market_regime.py`
- `src/strategy_baostock.py`
- `src/portfolio.py`

### 核心脚本

- `scripts/daily_run_baostock.py`
- `scripts/backtest_baostock.py`
- `scripts/generate_web_data.py`

### 展示层

- `web/`
- `report_server.py`

## 已下线实现

以下旧实现已迁移到 `legacy/`：

- `legacy/src/data_fetcher.py`
- `legacy/src/data_fetcher_hybrid.py`
- `legacy/src/scoring.py`
- `legacy/src/scoring_enhanced.py`
- `legacy/src/strategy.py`
- `legacy/scripts/backtest.py`
- `legacy/scripts/daily_run.py`
- `legacy/scripts/backtest_akshare.py`
- `legacy/scripts/backtest_enhanced.py`
- `legacy/scripts/export_ranking_json.py`
- `legacy/scripts/fetch_all_data.py`
- `legacy/scripts/test_with_mock.py`

## 主目录脚本约定

`scripts/` 目录只保留以下类别：

- 每日运行
- 主线回测
- 前端数据生成
- 回测 JSON 生成
- 测试脚本

## 推荐命令

```bash
python scripts/daily_run_baostock.py
python scripts/backtest_baostock.py 20250101
python scripts/generate_web_data.py

cd web
npm run build
npm run preview
```

## 说明

- 当前仓库优先保障正式主线可运行，而非保留所有历史实验的可执行性
- 如需查看历史实现，请阅读 `legacy/README.md`
- 当前唯一正式技术架构说明见 `docs/TECHNICAL_SPEC.md`
