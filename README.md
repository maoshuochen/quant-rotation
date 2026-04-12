# 指数轮动量化系统 (Quant Rotation System)

基于多因子评分的指数轮动研究系统，支持 A 股主要宽基指数和行业指数的评分、排名、信号生成、回测和前端可视化。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements/base.txt
```

### 2. 配置参数

编辑 `config/universe.yaml` 和 `config/strategy.yaml` 配置监控指数和策略参数。

### 3. 运行

```bash
# 每日评分与调仓信号
python scripts/daily_run_baostock.py

# 回测
python scripts/backtest_baostock.py

# 生成前端数据
python scripts/generate_data.py
```

## 项目结构

```text
quant-rotation/
├── config/                  # 策略、指数池、运行参数
├── src/                     # 核心策略代码
│   └── legacy/              # 历史实现与备用工具
├── scripts/                 # 日跑、回测、数据生成入口
│   └── tools/               # 增量回测、报告服务等辅助脚本
├── web/                     # React 看板
│   ├── src/                 # 前端源码
│   ├── public/              # 前端静态数据源（由脚本生成）
│   └── dist/                # 构建输出（无需提交）
├── data/raw/                # 行情缓存
├── backtest_results/        # 回测结果
├── reports/                 # 报告产物
└── logs/                    # 运行日志
```

仓库约定：

- `src/`、`scripts/`、`config/`、`web/src/` 是需要重点维护的源码区。
- `src/legacy/` 仅保留历史实现参考，不属于当前正式运行链路。
- `web/public/` 是前端消费的数据入口，`scripts/generate_data.py` 会把 JSON 写到这里。
- `web/dist/`、`logs/`、`reports/agents/`、`outputs/` 都属于生成产物，不再作为主要版本内容维护。

## 因子体系

| 因子 | 权重 | 内容 |
|------|------|------|
| 估值 | 25% | PE/PB 分位、股息率 |
| 动量 | 20% | 6/12 月收益、相对强弱 |
| 趋势 | 20% | MA20/60 位置 |
| 波动 | 15% | 波动率、最大回撤、夏普 |
| 资金流 | 15% | 成交量、北向资金、ETF 份额 |
| 相对强弱 | 20% | 相对沪深 300 |

## 监控指数

- **核心宽基** (5 只): 沪深 300、中证 500、中证 1000、创业板指、科创 50
- **行业指数** (13 只): 消费、医药、科技、金融、制造、红利、军工、新能源、半导体、白酒、银行、证券、煤炭
- **卫星** (1 只): 恒生指数

## GitHub Pages

访问 https://maoshuochen.github.io/quant-rotation/ 查看实时看板。GitHub Pages 直接从 `web/dist/` 构建产物部署，不再把前端文件同步到仓库根目录。

## GitHub Actions 自动化

数据刷新工作流每天 UTC 19:00（北京时间凌晨 3 点）自动运行：
1. 获取最新 ETF 数据
2. 运行回测更新
3. 生成 `web/public/*.json`

前端部署工作流在 `main` 分支的 `web/**` 变更后自动执行，负责构建前端并发布到 GitHub Pages。

## 回测表现

**回测期间**: 2025-01-02 ~ 2026-04-10

| 指标 | 数值 |
|------|------|
| 总收益 | 28.48% |
| 年化收益 | 21.84% |
| 最大回撤 | -14.56% |
| 夏普比率 | 1.00 |
| 交易天数 | 306 |
| 调仓次数 | 59 |

*注：历史回测不代表未来表现，量化交易存在亏损风险。*

## 注意事项

- 本项目仅供学术研究和教育用途，不构成投资建议
- 历史回测数据基于 Baostock 免费数据源
- 实际交易需考虑交易成本、滑点等因素
- 投资有风险，入市需谨慎
