# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-04-01

### 🎉 全面优化版本

#### 新增功能

**数据源优化**
- 新增多数据源适配层 (Baostock, Tushare, AKShare)
- 新增统一数据获取器 `UnifiedDataFetcher`
- 新增缓存管理器 `CacheManager` (支持 Parquet + SQLite)
- 支持数据源自动切换和故障转移

**因子工程增强**
- 新增稳健归一化 (RobustScaler, QuantileTransformer)
- 新增因子中性化模块 (去除市场/市值影响)
- 新增 IC 分析功能 (Pearson/Spearman IC)
- 新增因子衰减测试

**风险管理增强**
- 新增 `RiskManager` 模块
- 新增 VaR/CVaR 计算
- 新增 Kelly 公式仓位管理
- 新增风险平价权重计算
- 新增波动率自适应仓位调整
- 新增时间止损机制

**样本外验证**
- 新增 `OutOfSampleValidator` 模块
- 支持 Walk-Forward 分析
- 支持参数敏感性测试
- 支持过拟合检测

#### 工程化改进

**DevOps**
- 新增 Dockerfile 和 docker-compose.yml
- 新增 GitHub Actions CI/CD 配置
- 新增 pre-commit hooks 配置
- 新增开发依赖 `requirements-dev.txt`

**测试**
- 新增数据源测试 `test_data_sources.py`
- 新增验证模块测试 `test_validation.py`
- 新增风险管理测试 `test_risk_manager.py`

#### 配置变更

- `pyproject.toml` 更新为更全面的项目配置
- 新增 `.pre-commit-config.yaml`
- 新增 `requirements-lock.txt` 锁定关键依赖版本

#### 破坏性变更

- 无 (向后兼容现有接口)

---

## [1.0.0] - 2026-03-31

### 🎉 初始发布版本

- 多因子评分系统
- 贝叶斯参数优化
- 回测框架
- React 前端看板
