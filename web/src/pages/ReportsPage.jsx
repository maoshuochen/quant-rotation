import React, { useState, useEffect } from 'react'

const REPORTS_API_BASE = import.meta.env.VITE_REPORTS_API_BASE || 'http://localhost:5001'

const ReportsPage = () => {
  const [reports, setReports] = useState([])
  const [selectedReport, setSelectedReport] = useState(null)

  useEffect(() => {
    fetch(`${REPORTS_API_BASE}/api/reports`)
      .then(res => res.json())
      .then(data => {
        setReports(data.reports || [])
        if (data.reports?.length) {
          setSelectedReport(data.reports[0])
        }
      })
      .catch(err => console.error('加载报告失败:', err))
  }, [])

  const handleDownload = (fileName) => {
    window.open(`${REPORTS_API_BASE}/reports/${fileName}`, '_blank')
  }

  if (reports.length === 0) {
    return (
      <div className="text-center py-20 text-zinc-400">
        <h2 className="text-xl mb-2">暂无报告</h2>
        <p>请先运行主线回测并启动报告服务</p>
        <code className="block mt-4 p-2 bg-zinc-800 rounded text-sm">python3 scripts/backtest_baostock.py 20250101</code>
      </div>
    )
  }

  return (
    <div className="p-4 max-w-7xl mx-auto">
      <h2 className="text-2xl font-bold mb-6">📊 可视化报告</h2>

      {/* 报告列表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {reports.map((report, index) => (
          <div
            key={index}
            className={`p-4 rounded-lg cursor-pointer transition ${
              selectedReport === report
                ? 'bg-zinc-800 border-2 border-blue-500'
                : 'bg-zinc-900 border border-zinc-800 hover:border-zinc-700'
            }`}
            onClick={() => setSelectedReport(report)}
          >
            <h3 className="font-semibold mb-1">{report.name}</h3>
            <p className="text-sm text-zinc-500 mb-2">{report.date}</p>
            <div className="flex gap-2 flex-wrap">
              {report.files.map((file, i) => (
                <span key={i} className="text-xs px-2 py-1 bg-blue-900/30 text-blue-300 rounded">{file.type}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 报告详情 */}
      {selectedReport && (
        <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
          <h3 className="text-lg font-semibold mb-4">{selectedReport.name} - 报告详情</h3>

          {/* 图表预览 */}
          <div className="mb-6">
            <h4 className="font-semibold mb-3">📈 图表预览</h4>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {selectedReport.files.filter(f => f.type === 'chart').map((file, i) => (
                <div key={i} className="p-4 bg-zinc-800 rounded-lg text-center">
                  <h5 className="text-sm mb-3 text-zinc-400">{file.name.replace('.png', '').replace('_', ' ')}</h5>
                  <img
                    src={`${REPORTS_API_BASE}/reports/${file.name}`}
                    alt={file.name}
                    className="w-full rounded mb-3"
                  />
                  <button
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm"
                    onClick={() => handleDownload(file.name)}
                  >
                    下载原图
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* 数据文件 */}
          <div>
            <h4 className="font-semibold mb-3">📁 数据文件</h4>
            {selectedReport.files.filter(f => f.type === 'data').map((file, i) => (
              <div key={i} className="flex justify-between items-center p-3 bg-zinc-800 rounded mb-2">
                <span className="text-sm">{file.name}</span>
                <button
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm"
                  onClick={() => handleDownload(file.name)}
                >
                  下载
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ReportsPage
