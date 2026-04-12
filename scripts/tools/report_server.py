#!/usr/bin/env python3
"""
报告 API 服务器

提供报告列表和文件访问
"""
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / 'reports'
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def scan_reports():
    """扫描报告目录"""
    reports = {}
    
    for file in REPORTS_DIR.iterdir():
        if file.suffix in ['.png', '.html', '.csv']:
            # 提取报告名称
            name_parts = file.stem.split('_')
            if len(name_parts) >= 3:
                report_name = '_'.join(name_parts[:-1])  # backtest_enhanced_20250101
                file_type = name_parts[-1] if name_parts[-1] in ['equity_curve', 'drawdown', 'monthly_heatmap', 'positions', 'trades', 'summary'] else 'other'
                
                if report_name not in reports:
                    reports[report_name] = {
                        'name': report_name,
                        'date': name_parts[-1] if len(name_parts) > 1 else '',
                        'files': []
                    }
                
                # 文件类型映射
                type_map = {
                    'equity_curve': 'chart',
                    'drawdown': 'chart',
                    'monthly_heatmap': 'chart',
                    'positions': 'chart',
                    'trades': 'data',
                    'summary': 'summary'
                }
                
                reports[report_name]['files'].append({
                    'name': file.name,
                    'type': type_map.get(file_type, 'other'),
                    'size': file.stat().st_size,
                    'modified': datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                })
    
    return list(reports.values())


@app.route('/api/reports')
def get_reports():
    """获取报告列表"""
    reports = scan_reports()
    
    # 按日期排序
    reports.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    return jsonify({'reports': reports})


@app.route('/reports/<path:filename>')
def serve_report(filename):
    """提供报告文件"""
    return send_from_directory(REPORTS_DIR, filename)


@app.route('/api/reports/<report_name>/download')
def download_report(report_name):
    """下载报告 ZIP"""
    # TODO: 打包报告为 ZIP
    return jsonify({'error': 'Not implemented'})


if __name__ == '__main__':
    print("📊 报告 API 服务器启动")
    print(f"📁 报告目录：{REPORTS_DIR}")
    print("🌐 访问：http://localhost:5001/api/reports")
    app.run(host='0.0.0.0', port=5001, debug=False)
