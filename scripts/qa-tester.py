#!/usr/bin/env python3
"""
QA Tester - 量化前端自动化测试脚本
"""
import subprocess
import json
import sys
from pathlib import Path

WEB_DIR = Path('/root/.openclaw/workspace/quant-rotation/web')
DIST_DIR = WEB_DIR / 'dist'

def run_cmd(cmd, cwd=None):
    """运行命令"""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, '', str(e)

def check_build():
    """检查构建"""
    print("🔨 检查构建...")
    success, out, err = run_cmd('npm run build', cwd=WEB_DIR)
    if success:
        print("   ✅ 构建成功")
        return True
    else:
        print(f"   ❌ 构建失败：{err[:200]}")
        return False

def check_assets():
    """检查静态资源"""
    print("📦 检查静态资源...")
    required = ['index.html', 'backtest.json', 'ranking.json']
    missing = []
    for f in required:
        if not (DIST_DIR / f).exists():
            missing.append(f)
    
    assets_dir = DIST_DIR / 'assets'
    if not assets_dir.exists() or not any(assets_dir.iterdir()):
        missing.append('assets/')
    
    if missing:
        print(f"   ❌ 缺失：{missing}")
        return False
    print("   ✅ 资源完整")
    return True

def has_nan(val):
    """检查是否有 NaN"""
    if val is None:
        return True
    if isinstance(val, float) and (val != val):
        return True
    return False

def check_data():
    """验证数据文件"""
    print("📊 验证数据文件...")
    has_issues = False
    
    # 检查 backtest.json
    backtest_file = DIST_DIR / 'backtest.json'
    if backtest_file.exists():
        try:
            with open(backtest_file) as f:
                data = json.load(f)
            assert 'summary' in data
            assert 'chart_data' in data
            assert len(data['chart_data']) > 0
            
            # 检查 NaN
            nan_count = 0
            for key, val in data['summary'].items():
                if has_nan(val):
                    nan_count += 1
            for pt in data['chart_data']:
                for k, v in pt.items():
                    if has_nan(v):
                        nan_count += 1
            
            if nan_count > 0:
                print(f"   ❌ backtest.json: 发现 {nan_count} 个 NaN 值")
                has_issues = True
            else:
                print(f"   ✅ backtest.json: {len(data['chart_data'])} 天数据，无 NaN")
        except Exception as e:
            print(f"   ❌ backtest.json 错误：{e}")
            return False
    else:
        print("   ❌ backtest.json 不存在")
        return False
    
    # 检查 ranking.json
    ranking_file = DIST_DIR / 'ranking.json'
    if ranking_file.exists():
        try:
            with open(ranking_file) as f:
                data = json.load(f)
            assert 'ranking' in data
            assert len(data['ranking']) > 0
            
            # 检查 NaN
            nan_count = 0
            for item in data['ranking']:
                if has_nan(item.get('score')):
                    nan_count += 1
                for k, v in item.get('factors', {}).items():
                    if has_nan(v):
                        nan_count += 1
            
            if nan_count > 0:
                print(f"   ❌ ranking.json: 发现 {nan_count} 个 NaN 值")
                has_issues = True
            else:
                print(f"   ✅ ranking.json: {len(data['ranking'])} 条记录，无 NaN")
            
            # 检查因子一致性
            if data.get('ranking') and data.get('factor_weights'):
                first_factors = set(data['ranking'][0].get('factors', {}).keys())
                weights_keys = set(data['factor_weights'].keys())
                
                # 找出在 factors 中实际存在的 key
                actual_keys = first_factors
                print(f"   📍 因子：{', '.join(actual_keys)}")
                
                # 检查不匹配
                missing_in_weights = actual_keys - weights_keys
                if missing_in_weights:
                    print(f"   ⚠️  警告：因子 {missing_in_weights} 在 weights 中缺失")
        except Exception as e:
            print(f"   ❌ ranking.json 错误：{e}")
            return False
    else:
        print("   ❌ ranking.json 不存在")
        return False
    
    return not has_issues

def check_server():
    """检查服务可用性"""
    print("🌐 检查服务...")
    
    checks = [
        ('http://localhost:3000/', '首页'),
        ('http://localhost:3000/ranking.json', 'ranking.json'),
        ('http://localhost:3000/backtest.json', 'backtest.json'),
    ]
    
    all_ok = True
    for url, name in checks:
        success, out, err = run_cmd(f'curl -s --max-time 5 {url} | head -c 100')
        if success and out:
            print(f"   ✅ {name}: OK")
        else:
            print(f"   ❌ {name}: 无法访问")
            all_ok = False
    
    return all_ok

def main():
    print("=" * 50)
    print("🧪 QA Test Report - 量化前端")
    print("=" * 50)
    print()
    
    results = {
        'build': check_build(),
        'assets': check_assets(),
        'data': check_data(),
        'server': check_server(),
    }
    
    print()
    print("=" * 50)
    
    if all(results.values()):
        print("✅ 所有测试通过！")
        return 0
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"❌ 失败：{', '.join(failed)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
