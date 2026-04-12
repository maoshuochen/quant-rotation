# 文档索引

**最后更新**: 2026-03-25

本目录中，当前正式文档只有以下两份：

- `PRD.md`: 当前产品说明
- `TECHNICAL_SPEC.md`: 当前唯一正式技术架构说明

其他文档大多是历史优化记录、实验方案或阶段性总结，可能包含已经下线的实现名称，不应作为当前主线的事实来源。

## 当前主线

- 数据入口：`src/data_fetcher_baostock.py`
- 策略入口：`src/strategy_baostock.py`
- 回测入口：`scripts/backtest_baostock.py`
- 前端数据入口：`scripts/generate_data.py`
- 前端应用：`web/`
- 运行产物：`web/public/`、`reports/`、`logs/`
- 历史实现：`src/legacy/`
