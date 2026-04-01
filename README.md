# 指数轮动量化系统 (Quant Rotation System)

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Data](https://img.shields.io/badge/Data-Baostock%2FAKShare%2FTushare-orange.svg)](https://akshare.akfamily.xyz/)
[![CI](https://github.com/maoshuochen/quant-rotation/actions/workflows/ci.yml/badge.svg)](https://github.com/maoshuochen/quant-rotation/actions)

基于多因子评分的指数轮动研究系统，支持 A 股主要宽基指数和行业指数的评分、排名、信号生成、回测和前端可视化。

---

## 📊 策略特点

### 当前正式链路
- **数据入口**: `src/data_fetcher_baostock.py` / `src/data_sources/unified_fetcher.py`
- **策略入口**: `src/strategy_baostock.py`
- **回测入口**: `scripts/backtest_baostock.py`
- **前端数据入口**: `scripts/generate_web_data.py`
- **前端应用**: `web/`

### 核心功能
- **主线因子体系**: 估值 + 动量 + 趋势 + 波动 + 资金流 + 相对强弱
- **自动评分排名**: 每日对监控指数进行综合评分
- **交易信号生成**: 基于排名生成买入/卖出信号
- **模拟回测**: 支持历史回测和绩效分析
- **实时看板**: React 前端可视化展示

### 新增功能 (v2.0)

**数据源优化**
- 多数据源适配层 (Baostock, Tushare, AKShare)
- 统一数据获取器 `UnifiedDataFetcher`
- 缓存管理器 `CacheManager` (Parquet + SQLite 双缓存)
- 数据源自动切换和故障转移

**因子工程增强**
- 稳健归一化 (RobustScaler, QuantileTransformer)
- 因子中性化 (去除市场/市值影响)
- IC 分析 (Pearson/Spearman IC, IC_IR)
- 因子衰减测试

**风险管理增强**
- VaR / CVaR 计算
- Kelly 公式仓位管理
- 风险平价权重计算
- 波动率自适应仓位调整
- 时间止损机制

**样本外验证**
- Walk-Forward 分析
- 参数敏感性测试
- 过拟合检测

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd quant-rotation
pip install -r requirements.txt
```

### 2. 配置参数

正式配置优先读取拆分后的：

- `config/universe.yaml`
- `config/strategy.yaml`
- `config/runtime.yaml`

若拆分配置不存在，才会回退到 `config/config.yaml`。

例如 `config/universe.yaml`:

```yaml
# 监控指数
indices:
  - code: "000300.SH"
    name: "沪深 300"
    etf: "510300"
  - code: "000905.SH"
    name: "中证 500"
    etf: "510500"
  # ... 更多指数
  - code: "000921.CSI"
    name: "周期指数"
    etf: "512340"
    enabled: false  # 旧代理 ETF 停更，已从正式池下线

# 因子权重
factor_weights:
  value: 0.25
  momentum: 0.20
  volatility: 0.15
  trend: 0.20
  flow: 0.15
  relative_strength: 0.20

# 策略参数
strategy:
  top_n: 5          # 持有数量
  buffer_n: 8       # 缓冲数量
  rebalance_weekly: true  # 周度调仓
```

### 3. 运行正式链路

#### 参数优化 (贝叶斯优化)
```bash
# 单目标优化 (夏普比率)
python scripts/optimize_params.py --trials 50

# 多目标优化 (综合评分)
python scripts/optimize_multi_objective.py --trials 50 --objective composite

# 验证优化结果
python scripts/verify_optimization.py
```

#### 每日评分与调仓信号
```bash
python scripts/daily_run_baostock.py
```

#### 回测
```bash
python scripts/backtest_baostock.py
```

#### 生成前端数据
```bash
python scripts/generate_web_data.py
```

### 4. 启动前端看板

```bash
cd web
npm install
npm run build
npm run preview  # http://localhost:4173
```

---

## 📁 项目结构

```
quant-rotation/
├── config/                  # 配置文件
│   ├── config.yaml         # 主配置
│   └── secrets.yaml        # 敏感信息（不上传）
├── src/                     # 正式主线代码
│   ├── data_fetcher_baostock.py  # 数据获取
│   ├── scoring_baostock.py       # 主线评分引擎
│   ├── market_regime.py          # 市场状态与动态权重
│   ├── strategy_baostock.py      # 主线策略逻辑
│   ├── portfolio.py              # 组合管理
│   ├── optimizer.py              # 贝叶斯优化器
│   ├── factor_engine.py          # 因子计算引擎
│   └── notifier.py               # 通知模块
├── scripts/                 # 正式脚本入口
│   ├── daily_run_baostock.py     # 每日运行
│   ├── backtest_baostock.py      # 主线回测
│   ├── optimize_params.py        # 参数优化 (单目标)
│   ├── optimize_multi_objective.py  # 多目标优化
│   ├── verify_optimization.py    # 优化结果验证
│   ├── generate_web_data.py      # 生成前端数据
│   ├── generate_backtest_json.py # 回测 JSON 产物
│   └── test_*.py                 # 主线测试脚本
├── tests/                   # 单元测试
│   ├── test_optimizer.py       # 优化器测试
│   ├── test_portfolio.py       # 组合测试
│   ├── test_factor_engine.py   # 因子引擎测试
│   └── test_scoring_baseline.py# 评分基线测试
├── web/                     # 前端看板
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── dist/               # 构建输出
│   └── package.json
├── report_server.py         # 报告静态服务
├── data/                    # 数据缓存
│   └── raw/
├── backtest_results/        # 回测结果
├── optimization_results/    # 优化结果 (不提交)
├── logs/                    # 日志文件
├── requirements.txt         # Python 依赖
├── requirements-lock.txt    # 锁定依赖版本
├── pyproject.toml           # 项目配置
├── .env.example             # 环境变量示例
└── README.md               # 本文档
```

---

## 📈 当前说明

- 当前仓库以“研究型策略系统”为定位，不宣称策略指标已达成产品化目标。
- `legacy/` 下保留历史版本与实验代码，仅供参考。
- 若文档与代码不一致，以本文件和 `src/*_baostock.py` / `scripts/*_baostock.py` 为准。
- 当前正式活跃池为 19 只指数；`000921.CSI -> 512340` 因代理 ETF 停更已下线保留记录。

## 📊 因子体系

### 1. 趋势因子 (40%) ⭐
- MA20 位置
- MA60 位置
- 金叉/死叉状态

### 2. 资金流因子 (40%) ⭐
- 成交量趋势
- 量价配合
- 成交金额趋势
- 流入强度
- 北向资金指标
- ETF 份额指标

### 3. 动量因子 (24%) ⭐
- 6 月收益率
- 相对强弱

### 4. 基本面因子 (8%)
- 财务指标

### 5. 估值因子 (5%)
- PE 历史分位
- PB 历史分位

### 6. 波动因子 (4%)
- 年化波动率
- 最大回撤
- 夏普比率

---

## 📊 当前回测表现

### 最新优化结果 (多目标贝叶斯优化 2025-01 ~ 2026-03)

**优化目标**: 综合评分 (夏普比率 40% + 回撤 30% + 收益 30%)

| 指标 | 数值 |
|------|------|
| 夏普比率 | 1.61 |
| 总收益率 | 39.0% |
| 最大回撤 | -8.4% |
| 卡玛比率 | 4.67 |

### 最优因子权重

| 因子 | 权重 | 说明 |
|------|------|------|
| trend | 40% | 趋势 - 均线位置 ⭐ |
| flow | 40% | 资金流 - 成交量/金额趋势 ⭐ |
| momentum | 24% | 动量 - 6 月收益率 ⭐ |
| fundamental | 8% | 基本面因子 |
| value | 5% | 估值 - 价格分位 |
| volatility | 4% | 波动 - 低波动高分 |

**回测期间**: 2025-01-01 ~ 2026-03-31

*注：优化器报告与实际回测结果一致，差异率 < 0.1%*

---

## 📝 当前说明

- 当前仓库以"研究型策略系统"为定位，不宣称策略指标已达成产品化目标。
- 当前正式活跃池为 19 只指数；`000921.CSI -> 512340` 因代理 ETF 停更已下线保留记录。
- **最新优化**: 2026-03-31 完成多目标贝叶斯优化，夏普比率提升至 1.61，总收益 39%，最大回撤 8.4%。
- **测试覆盖**: 已添加 optimizer、portfolio、factor_engine 单元测试。
- 若文档与代码不一致，以本文件和 `src/*_baostock.py` / `scripts/*_baostock.py` 为准。

---

## 🔧 数据源

### 运行测试
```bash
cd /Users/maoshuo/Projects/quant-rotation
source .venv/bin/activate
pytest tests/ -v
```

### 代码质量检查
```bash
# 代码格式化
black src/ scripts/ tests/

# 代码检查
flake8 src/ scripts/ tests/

# 类型检查
mypy src/
```

### 安装锁定依赖
```bash
pip install -r requirements-lock.txt
```

### 主要数据源
- **Baostock**: A 股历史行情（免费、稳定）
- **AKShare**: 北向资金、ETF 份额（免费、部分受限）

### 替代数据源
- **Tushare**: 完整财务数据（需积分）
- **Choice**: 机构级数据（付费）

---

## 🧪 运行测试

```bash
cd /Users/maoshuo/Projects/quant-rotation
source .venv/bin/activate
pytest tests/ -v
```

目前已有测试：
- `tests/test_optimizer.py` - 贝叶斯优化器、多目标优化器测试
- `tests/test_portfolio.py` - 模拟投资组合、止损机制测试
- `tests/test_factor_engine.py` - 因子计算引擎测试
- `tests/test_scoring_baseline.py` - 评分引擎基线测试

## 📦 依赖管理

```bash
# 安装标准依赖
pip install -r requirements.txt

# 安装锁定版本（推荐，经过测试）
pip install -r requirements-lock.txt

# 安装开发工具
pip install pytest black flake8 mypy
```

## 🌐 前端看板

访问 http://localhost:4173 查看：

1. **排名页面**: 指数评分排名
2. **因子分析**: 雷达图 + 柱状图
3. **资金流详情**: 6 个子因子详解
4. **回测结果**: 净值曲线 + 绩效指标

---

## 📝 当前优化方向

### 已完成 (2026-03-31)
- [x] 多目标贝叶斯优化实现
- [x] 优化结果验证机制
- [x] 核心模块单元测试
- [x] 项目配置现代化 (pyproject.toml)
- [x] 依赖版本锁定
- [x] 文档清理与整合

### 短期优化
- [ ] 优化 ETF 份额数据源
- [ ] 添加更多 ETF 监控
- [ ] 改进因子归一化方法
- [ ] 样本外验证

### 中期计划
- [ ] 主线回测框架统一
- [ ] 动态权重效果验证
- [ ] 首页重构为“建议持仓 + 调仓解释”
- [ ] 报告产物协议标准化

### 长期规划
- [ ] 多策略框架
- [ ] 机器学习因子挖掘
- [ ] 分布式回测引擎

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 📧 联系方式

- 项目 Issue: https://github.com/maoshuochen/quant-rotation/issues
- 作者 GitHub: https://github.com/maoshuochen

---

## ⚠️ 风险提示

本项目仅供学术研究和教育用途，不构成投资建议。

- 历史回测不代表未来表现
- 量化交易存在亏损风险
- 使用本软件产生的任何问题由使用者自行承担

**投资有风险，入市需谨慎！**

---

*最后更新：2026-03-31*

---

## 📁 项目结构 (v2.0)

```
quant-rotation/
├── src/
│   ├── data_fetcher_baostock.py   # 主数据获取 (Baostock)
│   ├── data_sources/              # 多数据源适配层 (新增)
│   │   ├── __init__.py
│   │   ├── base.py                # 抽象基类
│   │   ├── baostock_adapter.py    # Baostock 适配器
│   │   ├── tushare_adapter.py     # Tushare 适配器
│   │   ├── akshare_adapter.py     # AKShare 适配器
│   │   ├── cache_manager.py       # 缓存管理器
│   │   └── unified_fetcher.py     # 统一数据获取器
│   ├── factor_engine.py           # 因子计算引擎
│   ├── factor_analysis.py         # 因子分析 (新增)
│   ├── scoring_baostock.py        # 评分引擎
│   ├── strategy_baostock.py       # 策略逻辑
│   ├── portfolio.py               # 组合管理
│   ├── risk_manager.py            # 风险管理 (新增)
│   ├── validation.py              # 样本外验证 (新增)
│   └── notifier.py                # 通知模块
├── scripts/
├── tests/
│   ├── test_optimizer.py
│   ├── test_portfolio.py
│   ├── test_factor_engine.py
│   ├── test_data_sources.py       # 数据源测试 (新增)
│   ├── test_validation.py         # 验证测试 (新增)
│   ├── test_risk_manager.py       # 风险测试 (新增)
├── web/
├── config/
├── Dockerfile                     # Docker 配置 (新增)
├── docker-compose.yml             # Docker Compose (新增)
├── .pre-commit-config.yaml        # Pre-commit hooks (新增)
├── .github/workflows/ci.yml       # CI/CD (新增)
├── requirements.txt
├── requirements-dev.txt           # 开发依赖 (新增)
└── pyproject.toml
```

---

## 🐳 Docker 部署

### 快速启动

```bash
# 构建并运行
docker-compose up -d

# 查看日志
docker-compose logs -f quant-rotation

# 停止服务
docker-compose down
```

### 手动 Docker

```bash
# 构建镜像
docker build -t quant-rotation:latest .

# 运行容器
docker run --rm -v $(pwd)/data:/app/data quant-rotation:latest python scripts/daily_run_baostock.py
```

---

## 🧪 测试

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_risk_manager.py -v
pytest tests/test_validation.py -v
pytest tests/test_data_sources.py -v

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

### Pre-commit Hooks

```bash
# 安装 pre-commit
pip install pre-commit
pre-commit install

# 手动运行所有 hooks
pre-commit run --all-files
```

---

## 🔧 配置数据源

### 使用 Tushare (可选)

Tushare 提供更高质量的财务数据，需要积分才能访问。

```bash
# 设置环境变量
export TUSHARE_TOKEN=your_tushare_token_here
```

系统会自动检测 `TUSHARE_TOKEN` 环境变量，如果设置则优先使用 Tushare 数据源。

### 数据源优先级

1. **Tushare** (如果有 token) - 数据质量最高
2. **Baostock** - 主力免费数据源
3. **AKShare** - 补充数据源 (北向资金、ETF 份额)

---

## 📈 新增 API 示例

### 统一数据获取

```python
from src.data_sources import UnifiedDataFetcher

fetcher = UnifiedDataFetcher(enable_cache=True)

# 获取历史行情 (自动选择最优数据源)
df = fetcher.fetch_price_history("000300.SH", "20240101")

# 获取指数 PE 历史
pe_df = fetcher.fetch_index_pe_history("000300.SH", "20240101")

# 获取北向资金
north_df = fetcher.fetch_northbound_flow("20250101")

# 获取 ETF 份额
etf_df = fetcher.fetch_etf_shares("510300", "20250101")
```

### 因子分析

```python
from src.factor_engine import FactorEngine
from src.factor_analysis import FactorAnalyzer

engine = FactorEngine()
analyzer = FactorAnalyzer(method='robust')

# 归一化因子
normalized = analyzer.normalize(factor_series)

# 中性化因子
neutralized = analyzer.neutralize(factor_series, benchmark_returns)

# 计算 IC
ic, ic_ir = analyzer.calc_ic(factor_series, forward_returns)

# 因子衰减
decay = engine.factor_decay_analysis(factor_series, returns, periods=[1, 5, 10])
```

### 风险管理

```python
from src.risk_manager import RiskManager

manager = RiskManager(
    target_volatility=0.15,
    use_kelly=True
)

# 计算 VaR / CVaR
var_95 = manager.calc_var(returns, confidence=0.95)
cvar_95 = manager.calc_cvar(returns, confidence=0.95)

# 获取完整风险指标
metrics = manager.get_risk_metrics(returns, prices)
print(f"VaR(95%): {metrics.var_95:.2%}")
print(f"Max DD: {metrics.max_drawdown:.2%}")
print(f"Sharpe: {metrics.sharpe_ratio:.2f}")

# Kelly 仓位
kelly = manager.calc_kelly_fraction(win_rate=0.6, win_loss_ratio=2.0)

# 风险平价权重
weights = manager.calc_risk_parity_weights(cov_matrix)
```

### 样本外验证

```python
from src.validation import OutOfSampleValidator

validator = OutOfSampleValidator(train_ratio=0.7)

# 简单训练/测试分割
train, test = validator.simple_train_test_split(data)

# Walk-Forward 分析
wf_result = validator.walk_forward_analysis(
    data,
    backtest_func=backtest,
    train_window=252,
    step_size=21,
    test_window=63
)

print(f"OOS Score: {wf_result.oos_score:.3f}")
print(f"Decay Ratio: {wf_result.decay_ratio:.1%}")

# 参数敏感性
sensitivity = validator.parameter_sensitivity(
    data, backtest_func,
    param_name='top_n',
    param_range=[3, 5, 7, 10],
    base_params={'top_n': 5}
)
```

---

## 📝 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

### v2.0.0 (2026-04-01)
- ✅ 多数据源适配层
- ✅ 因子工程增强
- ✅ 风险管理模块
- ✅ 样本外验证
- ✅ Docker/CI-CD 支持

### v1.0.0 (2026-03-31)
- 初始发布版本

---

*最后更新：2026-04-01*
