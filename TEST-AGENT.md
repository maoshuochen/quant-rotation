# 量化页面测试 Agent

## 职责
每次后端或前端代码改动后，自动执行测试验证。

## 测试清单

### 1. 数据生成测试
```bash
cd /root/.openclaw/workspace/quant-rotation
python3 scripts/generate_web_data.py
```
**验证点**：
- ✅ 脚本无报错
- ✅ 生成 `web/dist/ranking.json`
- ✅ 至少 15 个指数
- ✅ 因子得分不全为 0.5（动量/趋势/估值需有变化）

### 2. 回测测试
```bash
python3 scripts/backtest_baostock.py
python3 scripts/generate_backtest_json.py
```
**验证点**：
- ✅ 回测无报错
- ✅ 生成 `web/dist/backtest.json`
- ✅ 有合理的收益率和回撤数据

### 3. 前端页面测试
```bash
# 启动服务
cd web/dist
npx serve . -l 8080
```
**验证点**：
- ✅ 页面可访问
- ✅ 排名表格显示正常
- ✅ 因子得分有颜色区分
- ✅ 回测页面有图表

### 4. 数据质量检查
```python
import json
with open('web/dist/ranking.json') as f:
    data = json.load(f)
    
# 检查因子得分
for item in data['ranking'][:5]:
    factors = item['factors']
    assert factors['momentum'] != 0.5 or factors['trend'] != 0.5 or factors['value'] != 0.5, "因子得分异常"
```

## 触发时机
- 修改 `src/*.py` 后
- 修改 `scripts/*.py` 后
- 修改 `web/src/*` 或 `web/dist/*` 后
- 修改 `config/config.yaml` 后

## 快速测试命令
```bash
cd /root/.openclaw/workspace/quant-rotation
python3 scripts/generate_web_data.py && echo "✅ 数据生成成功" || echo "❌ 数据生成失败"
```
