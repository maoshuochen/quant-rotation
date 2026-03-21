# 安装部署指南

## 系统要求

- Python 3.9+
- Node.js 16+
- 内存：2GB+
- 存储：1GB+

---

## 一、后端安装

### 1. 克隆仓库

```bash
git clone https://github.com/maoshuochen/quant-rotation.git
cd quant-rotation
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 4. 验证安装

```bash
python -c "import akshare; print(akshare.__version__)"
python -c "import baostock; print('Baostock OK')"
```

---

## 二、前端安装

### 1. 安装 Node.js 依赖

```bash
cd web
npm install
```

### 2. 构建前端

```bash
npm run build
```

### 3. 启动开发服务器

```bash
npm run dev
```

### 4. 访问页面

打开浏览器访问：http://localhost:5173

---

## 三、配置说明

### 1. 主配置文件

编辑 `config/config.yaml`:

```yaml
# 监控指数列表
indices:
  - code: "000300.SH"
    name: "沪深 300"
    etf: "510300"
  - code: "000905.SH"
    name: "中证 500"
    etf: "510500"
  - code: "000852.SH"
    name: "中证 1000"
    etf: "512100"
  - code: "000388.SH"
    name: "科创 50"
    etf: "588000"
  - code: "000933.CSI"
    name: "医药指数"
    etf: "512010"
  - code: "000037.SH"
    name: "上证红利"
    etf: "510880"

# 因子权重（总和可超过 1，会自动归一化）
factor_weights:
  value: 0.25           # 估值
  momentum: 0.20        # 动量
  volatility: 0.15      # 波动
  trend: 0.20           # 趋势
  flow: 0.15            # 资金流
  relative_strength: 0.20  # 相对强弱

# 策略参数
strategy:
  top_n: 5              # 持有数量
  buffer_n: 8           # 缓冲数量（跌出前 N 才卖出）
  rebalance_weekly: true  # 周度调仓

# 模拟账户
portfolio:
  initial_capital: 1000000  # 初始资金 100 万
  commission: 0.0003        # 手续费万 3
  slippage: 0.001           # 滑点 0.1%
```

### 2. 敏感配置（可选）

创建 `config/secrets.yaml`（不上传 Git）:

```yaml
# Telegram 通知（可选）
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

# 数据库（可选）
database:
  url: "sqlite:///data/quant.db"
```

---

## 四、运行流程

### 1. 首次运行

```bash
# 获取历史数据
python scripts/fetch_all_data.py

# 运行回测
python scripts/backtest_baostock.py

# 生成前端数据
python scripts/generate_web_data.py
```

### 2. 每日运行

```bash
# 每日评分和信号生成
python scripts/daily_run_baostock.py

# 查看日志
tail -f logs/rotation.log
```

### 3. 定时任务（可选）

添加 Crontab:

```bash
crontab -e

# 每周一 9:00 运行
0 9 * * 1 cd /path/to/quant-rotation && /path/to/venv/bin/python scripts/daily_run_baostock.py >> logs/cron.log 2>&1
```

---

## 五、前端部署

### 开发环境

```bash
cd web
npm run dev
```

### 生产环境

```bash
# 构建
cd web
npm run build

# 使用 Nginx 托管
sudo cp -r dist/* /var/www/quant-rotation/
sudo systemctl restart nginx
```

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name quant.example.com;
    
    root /var/www/quant-rotation;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API 代理（如需）
    location /api/ {
        proxy_pass http://localhost:8000;
    }
}
```

---

## 六、数据源配置

### Baostock（主要）

无需配置，直接使用：

```python
import baostock as bs
bs.login()
```

### AKShare（辅助）

```bash
pip install akshare --upgrade
```

### Tushare（可选升级）

1. 注册 https://tushare.pro/
2. 获取 token
3. 添加到 `config/secrets.yaml`:

```yaml
tushare:
  token: "YOUR_TOKEN"
```

---

## 七、故障排查

### 问题 1: 数据获取失败

```bash
# 检查网络连接
ping www.baostock.com

# 检查库版本
pip show baostock akshare

# 升级库
pip install --upgrade baostock akshare
```

### 问题 2: 前端构建失败

```bash
# 清理缓存
cd web
rm -rf node_modules package-lock.json
npm install
```

### 问题 3: 评分结果为空

```bash
# 检查数据缓存
ls -lh data/raw/

# 手动获取数据
python -c "from src.data_fetcher_baostock import IndexDataFetcher; f = IndexDataFetcher(); print(f.fetch_etf_history('510300'))"
```

---

## 八、性能优化

### 1. 数据缓存

数据自动缓存在 `data/raw/` 目录，避免重复请求。

### 2. 并行处理（待实现）

```bash
# 未来版本支持
python scripts/daily_run_baostock.py --parallel
```

### 3. 数据库（待实现）

使用 SQLite/PostgreSQL 替代 CSV 缓存。

---

## 九、更新日志

### v0.2.0 (2026-03-21)
- ✅ 新增资金流因子（北向资金+ETF 份额）
- ✅ 前端资金流详情展示
- ✅ 修复 ETF 份额数据源

### v0.1.0 (2026-03-17)
- ✅ MVP 版本发布
- ✅ 6 大因子体系
- ✅ 基础回测功能
- ✅ React 前端看板

---

## 十、获取帮助

- 查看文档：`README.md`, `FACTOR_DOCS.md`
- 提交 Issue: https://github.com/maoshuochen/quant-rotation/issues
- 查看测试：`scripts/test_*.py`

---

*文档更新时间：2026-03-21*
