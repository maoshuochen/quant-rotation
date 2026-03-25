# 前端可视化报告页面 - 集成指南

## 概述

已在现有量化看板 (端口 3000) 中集成可视化报告页面。

---

## 🎯 新增功能

### 1. 报告页面 Tab

在量化看板顶部导航栏新增**"报告"**Tab，点击可查看：
- 报告列表
- 图表预览 (权益曲线/回撤/月度 heatmap/持仓分布)
- 综合 HTML 报告 (内嵌查看)
- 数据文件下载

---

## 📁 新增文件

```
quant-rotation/
├── web/src/
│   ├── ReportsPage.jsx          # 报告页面组件
│   └── App.jsx                  # 已修改 (添加报告 Tab)
├── report_server.py              # Flask API 服务器 (端口 5001)
└── reports/                      # 报告文件目录
    ├── *.png                     # 图表
    ├── *.html                    # 综合报告
    └── *.csv                     # 数据文件
```

---

## 🚀 使用方法

### 1. 启动服务

**前端 (已运行)**:
```bash
# 端口 3000
cd /root/.openclaw/workspace/quant-rotation/web
npm run dev
```

**后端 API (新启动)**:
```bash
# 端口 5001
cd /root/.openclaw/workspace/quant-rotation
python3 report_server.py
```

### 2. 访问看板

浏览器打开：**http://localhost:3000**

点击顶部导航栏的**"报告"**Tab

---

## 📊 报告页面功能

### 报告列表
- 显示所有回测报告
- 按日期排序 (最新在前)
- 点击报告卡片查看详情

### 图表预览
- 权益曲线图
- 回撤分析图
- 月度收益 heatmap
- 持仓分布图
- 支持下载原图

### 综合报告
- 内嵌 HTML 报告
- 包含所有图表和指标
- 响应式设计

### 数据文件
- 权益曲线 CSV
- 交易记录 CSV
- 支持下载

---

## 🔧 生成报告

### 方法 1: 回测后自动生成

```bash
cd /root/.openclaw/workspace/quant-rotation
python3 scripts/backtest_enhanced.py 20250101 20260324
# 完成后自动调用 visualizer.py 生成报告
```

### 方法 2: 手动生成

```bash
python3 src/visualizer.py
```

### 方法 3: 修改现有回测脚本

在 `backtest_enhanced.py` 结尾添加：

```python
# 生成可视化报告
from src.visualizer import ReportGenerator

generator = ReportGenerator()
generator.generate_all(
    equity_curve=equity_df,
    trades=trades_df,
    report_name=f"backtest_{start_date}"
)
```

---

## 🌐 API 端点

### GET /api/reports
获取报告列表

**响应**:
```json
{
  "reports": [
    {
      "name": "backtest_enhanced_20250101",
      "date": "20250101",
      "files": [
        {"name": "equity_curve.png", "type": "chart"},
        {"name": "summary.html", "type": "summary"},
        {"name": "data.csv", "type": "data"}
      ]
    }
  ]
}
```

### GET /reports/<filename>
下载报告文件

---

## 🎨 自定义样式

### 修改主题色

编辑 `ReportsPage.jsx`:

```javascript
// 卡片选中状态
reportCardSelected: {
  boxShadow: '0 4px 12px rgba(66, 153, 225, 0.5)',
  border: '2px solid #4299e1'  // 改为你喜欢的颜色
}

// 下载按钮
downloadBtn: {
  background: '#4299e1'  // 改为你的主题色
}
```

### 修改布局

```javascript
chartGrid: {
  gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))'
  // 改为 minmax(300px, 1fr) 显示更多列
}
```

---

## 📱 响应式设计

报告页面已支持：
- ✅ 桌面端 (1400px+)
- ✅ 平板端 (768px-1400px)
- ✅ 手机端 (<768px)

图表自动换行，卡片自适应宽度。

---

## 🔍 故障排除

### 问题 1: 报告列表为空

**检查**:
```bash
# 1. 确认报告文件存在
ls -lh /root/.openclaw/workspace/quant-rotation/reports/

# 2. 检查 API 服务器
curl http://localhost:5001/api/reports

# 3. 查看服务器日志
ps aux | grep report_server
```

---

### 问题 2: 图片无法加载

**原因**: 跨域问题或路径错误

**解决**:
```bash
# 检查 Flask 服务器是否运行
netstat -tlnp | grep 5001

# 检查 CORS 配置
cat report_server.py | grep CORS
```

---

### 问题 3: 页面不更新

**原因**: Vite 缓存

**解决**:
```bash
# 强制刷新浏览器
Ctrl + Shift + R (Windows/Linux)
Cmd + Shift + R (Mac)

# 或清除缓存
rm -rf /root/.openclaw/workspace/quant-rotation/web/node_modules/.vite
npm run dev  # 重启
```

---

## 🎯 下一步优化

### 短期
1. **因子贡献分解图** - 展示各因子对收益的贡献
2. **对比模式** - 并排对比多个回测报告
3. **导出 PDF** - 一键导出完整报告

### 中期
4. **实时回测** - 在页面中直接运行回测
5. **参数调整** - 交互式调整策略参数
6. **预警系统** - 达到阈值发送邮件/Telegram

### 长期
7. **多用户支持** - 不同用户不同回测组合
8. **云端存储** - 报告上传到云存储
9. **分享链接** - 生成公开分享链接

---

## 📝 技术栈

- **前端**: React + Vite + Tailwind CSS
- **图表**: Recharts (现有) + 原生 img (报告)
- **后端**: Flask + Flask-CORS
- **可视化**: Matplotlib + Seaborn

---

*完成时间：2026-03-24 23:30*
