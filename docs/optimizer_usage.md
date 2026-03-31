# 参数优化模块使用说明

## 贝叶斯优化器

基于贝叶斯优化的策略参数自动搜索工具，通过最小化试验次数找到最优参数组合。

### 安装依赖

```bash
pip install scikit-optimize
```

### 使用方法

#### 1. 因子权重优化

优化目标：最大化夏普比率

```bash
cd /Users/maoshuo/Projects/quant-rotation
source .venv/bin/activate

# 优化因子权重 (20 次试验，约 2 分钟)
python scripts/optimize_params.py --type factor_weights --trials 20
```

#### 2. 策略参数优化

优化 top_n, buffer_n, 动量窗口等策略参数：

```bash
python scripts/optimize_params.py --type strategy --trials 30
```

#### 3. 止损参数优化

优化止损阈值和冷却期：

```bash
python scripts/optimize_params.py --type stop_loss --trials 25
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| --start | 20250101 | 回测开始日期 |
| --end | 20260331 | 回测结束日期 |
| --trials | 50 | 优化试验次数 |
| --type | strategy | 优化类型 (strategy/factor_weights/stop_loss) |

### 输出结果

优化结果保存在 `optimization_results/` 目录：

- `best_params_*.yaml`: 最优参数配置
- `trial_history_*.csv`: 完整试验历史

### 优化结果示例

```
============================================================
贝叶斯优化结果
============================================================
优化指标：sharpe
试验次数：20
优化时间：107.4 秒

最优参数:
  value_weight: 0.0000
  momentum_weight: 0.0787
  trend_weight: 0.4000
  flow_weight: 0.1370
  volatility_weight: 0.0379
  fundamental_weight: 0.2000
  sentiment_weight: 0.2000

最优得分：1.3026
============================================================
```

### 注意事项

1. **优化时间**: 每次试验需要运行完整回测，建议 trial 数控制在 20-50 次
2. **过拟合风险**: 优化结果需要在样本外数据验证
3. **数据缓存**: 首次运行会下载数据，后续使用缓存 (位于 `data/cache/`)
4. **随机种子**: 设置 random_state=42 确保结果可复现

### 自定义优化目标

编辑 `src/optimizer.py` 中的 `_extract_metrics` 方法：

```python
def _extract_metrics(self, backtest_result: Dict) -> float:
    # 默认使用夏普比率
    return backtest_result.get('sharpe', 0.0)

    # 可改为其他指标:
    # return backtest_result.get('total_return', 0.0)  # 总收益
    # return backtest_result.get('calmar', 0.0)        # 卡玛比率
    # return -backtest_result.get('max_drawdown', 0.0) # 最小化回撤
```

### 添加新的参数空间

在 `src/optimizer.py` 中添加：

```python
def get_custom_param_space() -> List[ParameterSpace]:
    return [
        ParameterSpace('param_name', 'real', low=0.0, high=1.0),
        ParameterSpace('integer_param', 'integer', low=1, high=10),
        ParameterSpace('category_param', 'categorical', categories=['A', 'B', 'C']),
    ]
```
