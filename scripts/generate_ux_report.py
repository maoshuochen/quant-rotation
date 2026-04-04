#!/usr/bin/env python3
"""
前端 UX 评估脚本
基于 FRONTEND_UX_CHECKLIST.md 检查清单进行评估
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import os

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_data_files() -> Dict:
    """检查数据文件"""
    dist_dir = root_dir / 'web' / 'dist'

    files_to_check = ['ranking.json', 'history.json', 'backtest.json']
    results = {}

    for filename in files_to_check:
        filepath = dist_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            try:
                with open(filepath) as f:
                    data = json.load(f)
                results[filename] = {
                    'exists': True,
                    'valid': True,
                    'size_kb': round(size / 1024, 1),
                    'structure_ok': True
                }
            except json.JSONDecodeError:
                results[filename] = {
                    'exists': True,
                    'valid': False,
                    'size_kb': round(size / 1024, 1),
                    'structure_ok': False,
                    'error': 'Invalid JSON'
                }
        else:
            results[filename] = {
                'exists': False,
                'valid': False,
                'error': 'File not found'
            }

    return results


def check_data_consistency() -> Dict:
    """检查数据一致性"""
    dist_dir = root_dir / 'web' / 'dist'
    config_file = root_dir / 'config' / 'strategy.yaml'

    result = {
        'factors_aligned': False,
        'weights_normalized': False,
        'active_factors': []
    }

    # 读取配置
    try:
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)
        active_factors = config.get('factor_model', {}).get('active_factors', [])
        factor_weights = config.get('factor_weights', {})
    except Exception as e:
        logger.warning(f"读取配置失败：{e}")
        return result

    # 读取 ranking.json
    ranking_file = dist_dir / 'ranking.json'
    if not ranking_file.exists():
        return result

    try:
        with open(ranking_file) as f:
            ranking_data = json.load(f)

        # 检查因子权重
        ranking_weights = ranking_data.get('factor_weights', {})

        # 检查活跃因子是否一致
        ranking_factors = set(ranking_weights.keys())
        config_factors = set(active_factors)

        result['factors_aligned'] = ranking_factors == config_factors
        result['active_factors'] = active_factors

        # 检查权重归一化
        total_weight = sum(ranking_weights.values())
        result['weights_normalized'] = abs(total_weight - 1.0) < 0.01

    except Exception as e:
        logger.warning(f"检查 ranking.json 失败：{e}")

    return result


def check_frontend_code() -> Dict:
    """检查前端代码质量"""
    src_dir = root_dir / 'web' / 'src'

    result = {
        'accessibility': {
            'aria_labels': 0,
            'alt_texts': 0,
            'semantic_html': True
        },
        'responsive': {
            'has_breakpoints': False,
            'mobile_classes': False
        },
        'interaction': {
            'hover_states': False,
            'loading_states': False,
            'error_handling': False
        }
    }

    # 检查主要组件
    components = ['App.jsx', 'pages/Dashboard.jsx', 'pages/HistoryPanel.jsx']

    for component in components:
        filepath = src_dir / component
        if not filepath.exists():
            continue

        try:
            with open(filepath) as f:
                content = f.read()

            # 检查 aria 标签
            aria_count = content.count('aria-')
            result['accessibility']['aria_labels'] += aria_count

            # 检查 alt 文本
            alt_count = content.count('alt=')
            result['accessibility']['alt_texts'] += alt_count

            # 检查响应式类名
            if 'sm:' in content or 'md:' in content or 'lg:' in content:
                result['responsive']['has_breakpoints'] = True

            # 检查移动端类名
            if 'sm:' in content:
                result['responsive']['mobile_classes'] = True

            # 检查悬停状态
            if 'hover:' in content:
                result['interaction']['hover_states'] = True

            # 检查加载状态
            if 'loading' in content.lower():
                result['interaction']['loading_states'] = True

            # 检查错误处理
            if 'error' in content.lower() or 'ErrorBoundary' in content:
                result['interaction']['error_handling'] = True

        except Exception as e:
            logger.warning(f"检查 {component} 失败：{e}")

    return result


def check_visual_design() -> Dict:
    """评估视觉设计"""
    css_file = root_dir / 'web' / 'src' / 'index.css'

    result = {
        'score': 3,
        'max_score': 5,
        'strengths': [],
        'improvements': []
    }

    if not css_file.exists():
        return result

    try:
        with open(css_file) as f:
            content = f.read()

        # 检查深色模式
        if 'dark' in content or 'zinc-950' in content:
            result['strengths'].append('深色模式设计')
            result['score'] += 0.5

        # 检查颜色对比度
        if 'zinc-400' in content and 'zinc-950' in content:
            result['strengths'].append('颜色对比度合理')
            result['score'] += 0.5

        # 检查响应式设计
        if 'sm:' in content or 'md:' in content:
            result['strengths'].append('响应式断点')
            result['score'] += 0.5

        # 检查动画
        if 'transition' in content or 'animate-' in content:
            result['strengths'].append('动画过渡效果')
            result['score'] += 0.5

        # 检查琥珀色主题
        if 'amber' in content:
            result['strengths'].append('品牌色强调')

        # 扣分项
        if content.count('!important') > 5:
            result['improvements'].append('减少 !important 使用')
            result['score'] -= 0.5

    except Exception as e:
        logger.warning(f"检查 CSS 失败：{e}")

    result['score'] = max(1, min(5, result['score']))
    return result


def generate_report():
    """生成 UX 评估报告"""
    logger.info("开始生成 UX 评估报告...")

    # 数据文件检查
    logger.info("检查数据文件...")
    files_check = check_data_files()

    # 数据一致性检查
    logger.info("检查数据一致性...")
    data_consistency = check_data_consistency()

    # 前端代码检查
    logger.info("检查前端代码...")
    code_check = check_frontend_code()

    # 视觉设计评估
    logger.info("评估视觉设计...")
    visual_design = check_visual_design()

    # 生成报告
    report = {
        "agent": "frontend_agent",
        "timestamp": datetime.now().isoformat(),
        "report_type": "ux_assessment",
        "files_check": files_check,
        "data_consistency": data_consistency,
        "ux_assessment": {
            "visual_design": visual_design,
            "accessibility": {
                "score": 3 if code_check['accessibility']['aria_labels'] > 5 else 2,
                "max_score": 5,
                "strengths": ["基础可访问性支持"] if code_check['accessibility']['aria_labels'] > 0 else [],
                "improvements": ["需增加更多 aria 标签"] if code_check['accessibility']['aria_labels'] < 10 else []
            },
            "responsive": {
                "score": 4 if code_check['responsive']['has_breakpoints'] else 3,
                "max_score": 5,
                "strengths": ["响应式断点"] if code_check['responsive']['has_breakpoints'] else [],
                "improvements": [] if code_check['responsive']['has_breakpoints'] else ["需增强移动端适配"]
            },
            "interaction": {
                "score": 4 if code_check['interaction']['hover_states'] else 3,
                "max_score": 5,
                "strengths": ["悬停效果"] if code_check['interaction']['hover_states'] else [],
                "improvements": ["可增加加载动画"] if not code_check['interaction']['loading_states'] else []
            }
        },
        "issues": [],
        "recommendations": [],
        "overall_status": "ok"
    }

    # 识别问题
    for filename, info in files_check.items():
        if not info['exists']:
            report['issues'].append({
                'type': 'missing_file',
                'severity': 'high',
                'description': f'{filename} 不存在',
                'suggested_fix': '重新生成数据文件'
            })
        elif not info['valid']:
            report['issues'].append({
                'type': 'invalid_json',
                'severity': 'high',
                'description': f'{filename} 格式错误',
                'suggested_fix': '修复 JSON 格式'
            })

    if not data_consistency['factors_aligned']:
        report['issues'].append({
            'type': 'data_mismatch',
            'severity': 'high',
            'description': '前端因子配置与后端不一致',
            'suggested_fix': '重新生成 ranking.json'
        })

    if not data_consistency['weights_normalized']:
        report['issues'].append({
            'type': 'weights_issue',
            'severity': 'medium',
            'description': '因子权重未归一化',
            'suggested_fix': '检查权重配置'
        })

    # 生成建议
    if code_check['accessibility']['aria_labels'] < 5:
        report['recommendations'].append({
            'category': 'accessibility',
            'priority': 'medium',
            'action': '增加更多 aria 标签以提升可访问性',
            'expected_impact': '改善屏幕阅读器支持'
        })

    if not code_check['responsive']['mobile_classes']:
        report['recommendations'].append({
            'category': 'responsive',
            'priority': 'low',
            'action': '增强移动端适配',
            'expected_impact': '提升小屏设备体验'
        })

    # 计算总体评分
    total_score = 0
    max_score = 0

    for key, assessment in report['ux_assessment'].items():
        total_score += assessment['score']
        max_score += assessment['max_score']

    percentage = (total_score / max_score * 100) if max_score > 0 else 0

    if percentage >= 90:
        grade = 'A'
    elif percentage >= 75:
        grade = 'B'
    elif percentage >= 60:
        grade = 'C'
    elif percentage >= 40:
        grade = 'D'
    else:
        grade = 'F'

    report['ux_score'] = {
        'total': total_score,
        'max': max_score,
        'percentage': round(percentage, 1),
        'grade': grade
    }

    # 确定总体状态
    if report['issues']:
        high_severity = sum(1 for i in report['issues'] if i['severity'] == 'high')
        if high_severity > 0:
            report['overall_status'] = 'error'
        else:
            report['overall_status'] = 'warning'

    # 保存到文件
    output_dir = root_dir / 'reports' / 'agents'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f'frontend_ux_report_{datetime.now().strftime("%Y%m%d")}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"报告已保存至：{output_file}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("前端 UX 评估报告摘要")
    print("=" * 60)

    print(f"\n数据文件检查:")
    for filename, info in files_check.items():
        status = "✅" if info.get('exists', False) else "❌"
        print(f"  {status} {filename}: {info.get('size_kb', 0)}KB")

    print(f"\n数据一致性:")
    print(f"  因子对齐：{'✅' if data_consistency['factors_aligned'] else '❌'}")
    print(f"  权重归一化：{'✅' if data_consistency['weights_normalized'] else '❌'}")
    print(f"  活跃因子：{data_consistency['active_factors']}")

    print(f"\nUX 评分:")
    print(f"  总分：{total_score}/{max_score} ({percentage:.1f}%)")
    print(f"  等级：{grade}")

    print(f"\n视觉设计：{visual_design['score']}/{visual_design['max_score']}")
    if visual_design['strengths']:
        print(f"  优点：{', '.join(visual_design['strengths'])}")
    if visual_design['improvements']:
        print(f"  改进：{', '.join(visual_design['improvements'])}")

    if report['issues']:
        print(f"\n发现问题 ({len(report['issues'])} 个):")
        for issue in report['issues'][:5]:
            print(f"  [{issue['severity'].upper()}] {issue['description']}")

    if report['recommendations']:
        print(f"\n优化建议 ({len(report['recommendations'])} 条):")
        for rec in report['recommendations'][:3]:
            print(f"  - {rec['action']}")

    print(f"\n总体状态：{report['overall_status']}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    generate_report()
