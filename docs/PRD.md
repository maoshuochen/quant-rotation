# 指数轮动量化系统 - 产品说明

**版本**: v2.1  
**最后更新**: 2026-03-25  
**状态**: 主线可运行，持续优化中

## 一、产品定位

本项目当前定位为个人研究型指数轮动系统，而不是面向外部用户的完整资管产品。

目标是提供一条稳定、可解释、可复盘的正式运行链路：

- 每日/每周生成指数 ETF 排名与调仓建议
- 基于统一口径进行历史回测
- 通过 Web 看板和报告查看策略状态

## 二、当前正式功能

### F1: 指数评分与排名

- 输入：`config/config.yaml` 中的监控指数与权重配置
- 处理：通过 `src/data_fetcher_baostock.py` 获取数据，使用 `src/strategy_baostock.py` 串联评分逻辑
- 输出：指数排名、因子得分、调仓信号

### F2: 主线回测

- 入口：`scripts/backtest_baostock.py`
- 规则：前 5 持有、前 8 缓冲、按配置计算手续费和滑点
- 输出：回测净值序列、统计指标、CSV 结果

### F3: 前端数据生成

- 入口：`scripts/generate_web_data.py`
- 输出：`web/dist/ranking.json`、`web/dist/backtest.json`

### F4: Web 看板

- 入口：`web/`
- 页面：排名、因子、回测、报告

## 三、当前正式运行链路

1. `scripts/daily_run_baostock.py`
2. `scripts/backtest_baostock.py`
3. `scripts/generate_web_data.py`
4. `web/`
5. `report_server.py`

## 四、产品边界

- `legacy/` 目录中的代码不属于正式运行链路
- 实验性因子、历史实现、旧版回测脚本仅作参考
- 当前策略表现尚未达到产品化目标，所有结论仅用于研究和学习

## 五、下一步方向

- 主线回测指标持续优化
- 动态权重是否有效的对照验证
- 首页改造为“建议持仓 + 调仓解释”
- 报告资源命名与打包协议标准化
