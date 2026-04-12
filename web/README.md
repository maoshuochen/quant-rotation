# 指数轮动策略 - Web 仪表盘

## 功能

- 📊 指数排名展示
- 🔍 因子构成分析（雷达图 + 条形图）
- 📐 计算逻辑说明
- 📱 响应式设计

## 开发

```bash
cd web

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:3000
```

## 构建

```bash
# 生产构建
npm run build

# 预览构建结果
npm run preview
```

## 数据更新

前端数据以 `public/` 下的 JSON 为主，由正式脚本生成，构建时会自动打包进 `dist/`：

```bash
# 在项目根目录运行
python3 scripts/generate_data.py
```

## 自动化

可以配置 Cron 定时更新数据：

```bash
crontab -e

# 每天 9:00 更新数据
0 9 * * 1-5 cd /path/to/quant-rotation && python3 scripts/generate_data.py
```

## 技术栈

- React 18
- Vite 5
- Tailwind CSS 3
- Recharts (图表库)

## 页面结构

```
web/
├── src/
│   ├── App.jsx          # 主应用组件
│   ├── main.jsx         # 入口文件
│   └── index.css        # 样式文件
├── public/
│   ├── vite.svg         # 图标
│   └── *.json           # 前端静态数据
├── dist/
│   └── ...              # 构建输出（无需提交）
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## API 数据格式

`ranking.json` 格式：

```json
{
  "update_time": "2026-03-17 13:48:27",
  "data_source": "Baostock",
  "ranking": [
    {
      "rank": 1,
      "code": "000933.CSI",
      "name": "医药指数",
      "etf": "512010",
      "score": 0.7353,
      "factors": {
        "momentum": 0.5,
        "volatility": 0.754,
        "trend": 0.5,
        "value": 0.8889,
        "relative_strength": 1.0
      }
    }
  ],
  "factor_weights": {...},
  "strategy": {...}
}
```

---

最后更新：2026-03-25
