# 可视化报告使用指南

## 概述

可视化报告生成器提供 6 种图表和报告，帮助深入分析回测结果。

---

## 📊 报告类型

### 1. 权益曲线图 (`*_equity_curve.png`)

**内容**:
- 组合价值变化曲线
- 回撤填充图
- 每日收益柱状图

**解读**:
- 蓝色曲线向上 = 盈利
- 红色区域 = 回撤期间
- 绿色柱子 = 盈利日，红色 = 亏损日

![权益曲线示例](example_equity_curve.png)

---

### 2. 回撤分布图 (`*_drawdown.png`)

**内容**:
- 回撤直方图 (回撤幅度分布)
- 回撤持续时间分布

**解读**:
- 左侧峰值 = 小幅回撤频繁
- 右侧长尾 = 极端回撤事件
- 持续时间越短越好

---

### 3. 月度收益 Heatmap (`*_monthly_heatmap.png`)

**内容**:
- 12 个月 × 年份的收益矩阵
- 绿色 = 正收益，红色 = 负收益

**解读**:
- 深绿 = 大幅盈利 (>10%)
- 深红 = 大幅亏损 (<-10%)
- 观察季节性规律

**示例**:
```
        1 月   2 月   3 月   4 月   5 月   6 月   7 月   8 月   9 月   10 月  11 月  12 月
2025    +5.2  -2.1  +3.4  +1.8  -4.5  +2.3  +6.1  -1.2  +0.8  +3.5   +2.1   -1.5
2026    +2.1  +4.3  -0.5
```

---

### 4. 持仓分布图 (`*_positions.png`)

**内容**:
- 各 ETF 交易次数
- 买入/卖出比例
- 交易金额分布
- 交易成本分布

**解读**:
- 交易次数均匀 = 分散投资
- 买入>卖出 = 仓位增加
- 成本占比越低越好

---

### 5. 交易记录表 (`*_trades.html`)

**内容**:
- 完整交易记录 HTML 表格
- 日期、ETF 代码、买卖方向、份额、价格、金额、成本

**特点**:
- 可交互排序
- 支持搜索过滤
- 可直接在浏览器打开

---

### 6. 综合报告 HTML (`*_summary.html`)

**内容**:
- 核心指标卡片 (总收益/年化/夏普/回撤)
- 4 张图表嵌入
- 响应式设计

**特点**:
- 单文件分享友好
- 可直接发邮件附件
- 手机/电脑均可查看

---

## 🚀 使用方法

### 方法 1: 自动生成 (推荐)

回测完成后自动调用可视化：

```bash
cd /root/.openclaw/workspace/quant-rotation

# 运行回测 (会自动生成报告)
python3 scripts/backtest_enhanced.py 20250101 20260324
```

**输出位置**: `reports/` 目录

---

### 方法 2: 手动生成

已有回测数据，单独生成报告：

```bash
python3 src/visualizer.py
```

**前提**: `reports/backtest_enhanced_20250101.csv` 存在

---

### 方法 3: Python API 调用

```python
from src.visualizer import ReportGenerator
import pandas as pd

# 加载数据
equity_df = pd.read_csv('reports/backtest_enhanced_20250101.csv', 
                        index_col='date', parse_dates=True)
trades_df = pd.read_csv('reports/trades_enhanced_20250101.csv')

# 生成报告
generator = ReportGenerator(output_dir='reports')
generator.generate_all(
    equity_curve=equity_df,
    trades=trades_df,
    report_name='my_backtest_report'
)
```

---

### 方法 4: 单独生成某张图

```python
from src.visualizer import ReportGenerator
import pandas as pd

equity_df = pd.read_csv('reports/backtest_enhanced_20250101.csv',
                        index_col='date', parse_dates=True)

generator = ReportGenerator()

# 只生成权益曲线
generator.plot_equity_curve(equity_df, 'my_equity.png')

# 只生成回撤图
generator.plot_drawdown_distribution(equity_df, 'my_drawdown.png')

# 只生成月度 heatmap
generator.plot_monthly_returns(equity_df, 'my_heatmap.png')
```

---

## 📁 文件清单

一次完整回测 + 可视化会生成：

```
reports/
├── backtest_enhanced_20250101.csv      # 权益曲线数据 (CSV)
├── trades_enhanced_20250101.csv        # 交易记录数据 (CSV)
├── backtest_enhanced_20250101_equity_curve.png      # 权益曲线图
├── backtest_enhanced_20250101_drawdown.png          # 回撤分析图
├── backtest_enhanced_20250101_monthly_heatmap.png   # 月度收益 heatmap
├── backtest_enhanced_20250101_positions.png         # 持仓分布图
├── backtest_enhanced_20250101_trades.html           # 交易记录表
└── backtest_enhanced_20250101_summary.html          # 综合报告 ⭐
```

---

## 🎨 自定义样式

### 修改颜色方案

编辑 `src/visualizer.py`:

```python
# 权益曲线颜色
ax1.plot(df.index, df['equity'], 'b-', linewidth=1.5)  # 'b-' = 蓝色

# 回撤颜色
ax2.fill_between(df.index, df['drawdown']*100, 0, color='red', alpha=0.3)

# 月度 heatmap 颜色
sns.heatmap(returns_df, cmap='RdYlGn', ...)  # 'RdYlGn' = 红黄绿
```

**常用颜色映射**:
- `'RdYlGn'`: 红 - 黄-绿 (推荐)
- `'RdYlBu'`: 红 - 黄-蓝
- `'coolwarm'`: 冷 - 暖
- `'viridis'`: 渐变绿

### 修改图片尺寸

```python
fig, axes = plt.subplots(3, 1, figsize=(14, 10))  # 宽 14 英寸，高 10 英寸
```

### 修改 DPI (分辨率)

```python
plt.savefig(filepath, dpi=150, ...)  # 150 DPI (默认)
plt.savefig(filepath, dpi=300, ...)  # 300 DPI (打印质量)
```

---

## 📱 查看报告

### 本地查看

```bash
# 在浏览器打开综合报告
cd /root/.openclaw/workspace/quant-rotation/reports
firefox backtest_enhanced_20250101_summary.html
# 或
google-chrome backtest_enhanced_20250101_summary.html
```

### 发送到 Telegram

```python
# 使用 OpenClaw message 工具发送
# (需要在回测脚本中集成)
```

### 打印为 PDF

1. 在浏览器打开 HTML 报告
2. Ctrl+P (打印)
3. 选择"另存为 PDF"
4. 调整边距，保存

---

## 🔧 故障排除

### 问题 1: 中文字符显示为方框

**原因**: 系统缺少中文字体

**解决**:
```bash
# Ubuntu/Debian
sudo apt-get install fonts-wqy-zenhei fonts-wqy-microhei

# CentOS/RHEL
sudo yum install wqy-zenhei-fonts wqy-microhei-fonts

# macOS
# 已内置中文字体，无需安装
```

然后在 `visualizer.py` 中设置字体：
```python
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'Arial Unicode MS']
```

---

### 问题 2: 图片空白或报错

**可能原因**:
- 数据文件不存在
- 数据格式错误
- 缺少依赖库

**检查**:
```bash
# 检查数据文件
ls -lh reports/*.csv

# 检查依赖
pip3 list | grep -E "matplotlib|seaborn|pandas"

# 重新安装
pip3 install matplotlib seaborn pandas --upgrade
```

---

### 问题 3: 报告生成太慢

**优化建议**:
- 减少回测天数 (如只测最近 1 年)
- 降低图片 DPI (150 → 100)
- 减少图表数量 (只生成关键的)

---

## 📊 报告解读示例

### 示例 1: 权益曲线健康

```
✅ 曲线稳定向上
✅ 回撤幅度 < 10%
✅ 回撤恢复快 (< 30 天)
✅ 月度收益多数为正
```

**结论**: 策略有效，可实盘

---

### 示例 2: 权益曲线不健康

```
❌ 曲线震荡向下
❌ 回撤幅度 > 20%
❌ 长期无法恢复 (> 90 天)
❌ 月度收益波动大
```

**结论**: 策略需优化或放弃

---

### 示例 3: 识别季节性

```
观察月度 heatmap:
- 1-2 月经常盈利 (春节行情)
- 5-6 月经常亏损 (市场淡季)
- 11-12 月经常盈利 (年末行情)
```

**应用**: 季节性调整仓位

---

## 🎯 最佳实践

1. **每次回测必生成报告** - 可视化比数字更直观
2. **保存历史报告** - 便于策略迭代对比
3. **重点关注回撤** - 收益可以等，回撤会爆仓
4. **分享 HTML 报告** - 单文件包含所有信息
5. **定期复盘** - 每月查看月度 heatmap 找规律

---

## 📝 下一步

1. **因子贡献分解图** - 展示各因子对收益的贡献
2. **持仓时间分布** - 平均持仓多久
3. **胜率/盈亏比** - 交易质量分析
4. **对比基准** - 相对沪深 300 的超额收益

---

*完成时间：2026-03-24*
