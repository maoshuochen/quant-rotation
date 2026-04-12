# 指数轮动量化系统 (Quant Rotation System)

基于多因子评分的指数轮动研究系统，支持 A 股主要宽基指数和行业指数的评分、排名、信号生成、回测和前端可视化。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements/base.txt
```

### 2. 配置参数

编辑 `config/universe.yaml`、`config/strategy.yaml` 和 `config/runtime.yaml` 配置指数池、策略参数与运行设置。

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
├── site/                    # GitHub Pages 站点产物
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

当前正式主模型只使用 3 个主因子参与总分，权重来自 `config/strategy.yaml`：

| 因子 | 权重 | 内容 |
|------|------|------|
| 动量 | 24% | 近 6 个月收益率为主，辅以近 1 个月变化做归因展示 |
| 趋势 | 40% | 价格相对 MA20 / MA60 的位置 |
| 资金流 | 36% | 成交量趋势、量价配合、成交金额、北向资金、ETF 份额 |

补充说明：

- `估值`、`波动`、`相对强弱` 仍会在评分与归因中计算，但当前不计入主模型总分。
- 市场状态切换会影响看板展示和动态解释，但当前基线回测主分仍以上述 3 因子为核心。

## 监控指数

- **核心宽基** (5 只): 沪深 300、中证 500、中证 1000、创业板指、科创 50
- **行业指数** (13 只): 消费、医药、科技、金融、制造、红利、军工、新能源、半导体、白酒、银行、证券、煤炭
- **卫星** (1 只): 恒生指数

## GitHub Pages

访问 https://maoshuochen.github.io/quant-rotation/ 查看实时看板。仓库根目录的 `index.html` 只负责跳转，实际站点内容发布在 `site/`。

## GitHub Actions 自动化

数据刷新工作流每天 UTC 19:00（北京时间凌晨 3 点）自动运行：
1. 获取最新 ETF 数据
2. 运行回测更新
3. 生成 `web/public/*.json`

前端同步工作流在 `main` 分支的 `web/**` 变更后自动执行，负责构建前端并更新 `site/`。

## 回测表现

**回测期间**: 2024-01-02 ~ 2026-04-01

| 指标 | 数值 |
|------|------|
| 总收益 | 18.31% |
| 年化收益 | 7.77% |
| 最大回撤 | -20.05% |
| 夏普比率 | 0.44 |
| 交易天数 | 542 |
| 调仓次数 | 107 |

*注：历史回测不代表未来表现，量化交易存在亏损风险。*

## 注意事项

- 本项目仅供学术研究和教育用途，不构成投资建议
- 历史回测数据基于 Baostock 免费数据源
- 实际交易需考虑交易成本、滑点等因素
- 投资有风险，入市需谨慎
