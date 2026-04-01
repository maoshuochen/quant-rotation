# GitHub Actions 自动化回测配置指南

## 快速开始

### 1. 启用 GitHub Pages

1. 进入仓库 Settings → Pages
2. Source 选择 `Deploy from a branch`
3. Branch 选择 `gh-pages` 和 `/ (root)`
4. 保存

### 2. 配置 Telegram 通知 (可选)

1. 创建 Telegram Bot:
   - 联系 [@BotFather](https://t.me/BotFather)
   - 发送 `/newbot` 创建机器人
   - 获取 `BOT_TOKEN`

2. 获取 Chat ID:
   - 联系 [@userinfobot](https://t.me/userinfobot)
   - 发送任意消息获取 `chat_id`

3. 添加 GitHub Secrets:
   - Settings → Secrets and variables → Actions
   - 添加 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`

### 3. 手动触发回测

1. 进入 Actions → Daily Backtest
2. 点击 "Run workflow"
3. 选择分支 (默认 main)
4. 点击 "Run workflow"

### 4. 查看回测结果

- **GitHub Pages**: `https://maoshuochen.github.io/quant-rotation/data/`
- **Actions 日志**: Actions → Daily Backtest → 最近一次运行

---

## 调度时间说明

当前配置：
```yaml
schedule:
  - cron: '0 0 * * 1-5'  # 工作日 UTC 0 点 = 北京时间 8 点
```

修改建议：
- 每天运行：`0 0 * * *`
- 周一到周五：`0 0 * * 1-5`
- 每周一：`0 0 * * 1`

---

## 成本估算

GitHub Actions 免费额度：
- 每月 2000 分钟 (Public 仓库无限)
- 每次回测约 5-10 分钟
- 每月运行 22 天 (工作日) ≈ 110-220 分钟

远低于免费额度，无需付费。

---

## 故障排查

### 回测失败

1. 检查 Actions 日志
2. 确认数据源可用 (Baostock/AKShare)
3. 手动触发测试

### 数据未更新

1. 检查 gh-pages 分支是否创建
2. 确认 Pages 设置正确
3. 清除浏览器缓存

### Telegram 通知未发送

1. 检查 Secrets 配置
2. 测试 Bot Token 是否有效
3. 确认 Chat ID 正确
