# QA Tester Agent - 量化前端测试

## 职责

在代码更改后自动执行测试，确保功能正常。

## 测试清单

### 1. 构建检查
```bash
cd /root/.openclaw/workspace/quant-rotation/web
npm run build
```
- ✅ 构建成功无错误
- ✅ 输出文件生成在 `dist/` 目录

### 2. 静态资源检查
```bash
ls -la /root/.openclaw/workspace/quant-rotation/web/dist/
```
- ✅ `index.html` 存在
- ✅ `backtest.json` 存在（回测数据）
- ✅ `ranking.json` 存在（排名数据）
- ✅ `assets/` 目录有 JS/CSS 文件

### 3. 数据文件验证
```bash
python3 -c "
import json
with open('/root/.openclaw/workspace/quant-rotation/web/dist/backtest.json') as f:
    data = json.load(f)
    assert 'summary' in data
    assert 'chart_data' in data
    assert len(data['chart_data']) > 0
    print('backtest.json ✅')

with open('/root/.openclaw/workspace/quant-rotation/web/dist/ranking.json') as f:
    data = json.load(f)
    assert 'ranking' in data
    assert len(data['ranking']) > 0
    # 检查 factors 和 weights 一致性
    if data.get('ranking') and data.get('factor_weights'):
        first_factors = set(data['ranking'][0].get('factors', {}).keys())
        weights_keys = set(data['factor_weights'].keys())
        print(f'Factors: {first_factors}')
        print(f'Weights: {weights_keys}')
    print('ranking.json ✅')
"
```

### 4. 服务可用性检查
```bash
# 检查端口
curl -s http://localhost:3000/ | head -5
curl -s http://localhost:3000/ranking.json | python3 -m json.tool > /dev/null && echo "ranking.json OK"
curl -s http://localhost:3000/backtest.json | python3 -m json.tool > /dev/null && echo "backtest.json OK"
```

### 5. 关键功能验证
- ✅ 页面能正常加载（无白屏）
- ✅ 排名数据能显示
- ✅ 因子分析图表能渲染
- ✅ 回测图表能渲染
- ✅ 移动端标签切换正常

## 使用方式

### 完整测试
```
/test-quant-web
```

### 快速检查
```
/test-quant-web --quick
```

## 输出格式

```
🧪 QA Test Report - 量化前端

✅ Build: 成功
✅ Assets: 完整
✅ Data: 验证通过
✅ Server: 运行中 (port 3000)

📊 数据摘要:
- ranking.json: 6 条记录
- backtest.json: 531 天数据
- 因子数：5 (momentum, volatility, trend, value, relative_strength)

⚠️  警告：无

❌ 错误：无
```

## 自动修复建议

如果发现问题：
1. **构建失败** → 检查 npm 依赖 `npm install`
2. **数据缺失** → 运行生成脚本 `python3 scripts/generate_backtest_json.py`
3. **服务未启动** → 重启 `python3 -m http.server 3000`
4. **因子不匹配** → 检查 `ranking.json` 中 `factors` 和 `factor_weights` 的 key 一致性
