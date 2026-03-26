import React, { useState, useEffect } from 'react'

const REPORTS_API_BASE = import.meta.env.VITE_REPORTS_API_BASE || 'http://localhost:5001'

const ReportsPage = () => {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedReport, setSelectedReport] = useState(null)

  useEffect(() => {
    // 加载报告列表
    fetch(`${REPORTS_API_BASE}/api/reports`)
      .then(res => res.json())
      .then(data => {
        setReports(data.reports || [])
        if (!selectedReport && data.reports?.length) {
          setSelectedReport(data.reports[0])
        }
        setLoading(false)
      })
      .catch(err => {
        console.error('加载报告失败:', err)
        setLoading(false)
      })
  }, [])

  const handleViewReport = (report) => {
    setSelectedReport(report)
  }

  const handleDownload = (report) => {
    window.open(`${REPORTS_API_BASE}/reports/${report.file}`, '_blank')
  }

  if (loading) {
    return (
      <div style={styles.loading}>
        <div className="spinner">加载报告中...</div>
      </div>
    )
  }

  if (reports.length === 0) {
    return (
      <div style={styles.empty}>
        <h2>暂无报告</h2>
        <p>请先运行主线回测并启动报告服务</p>
        <code style={styles.code}>python3 scripts/backtest_baostock.py 20250101</code>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>📊 可视化报告</h2>
      
      {/* 报告列表 */}
      <div style={styles.reportList}>
        {reports.map((report, index) => (
          <div 
            key={index} 
            style={{
              ...styles.reportCard,
              ...(selectedReport === report ? styles.reportCardSelected : {})
            }}
            onClick={() => handleViewReport(report)}
          >
            <h3 style={styles.reportName}>{report.name}</h3>
            <p style={styles.reportDate}>{report.date}</p>
            <div style={styles.reportFiles}>
              {report.files.map((file, i) => (
                <span key={i} style={styles.fileTag}>{file.type}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 报告详情 */}
      {selectedReport && (
        <div style={styles.detail}>
          <h3>{selectedReport.name} - 报告详情</h3>
          
          {/* 综合报告 HTML */}
          {selectedReport.files.find(f => f.type === 'summary') && (
            <div style={styles.section}>
              <h4>📄 综合报告</h4>
              <div style={styles.summaryBox}>
                <p style={styles.summaryHint}>
                  报告摘要文件已生成。为避免旧版 HTML 的静态资源引用影响主页面，建议在新窗口查看。
                </p>
                <button
                  style={styles.downloadBtn}
                  onClick={() => handleDownload({ file: selectedReport.files.find(f => f.type === 'summary').name })}
                >
                  打开摘要报告
                </button>
              </div>
            </div>
          )}

          {/* 图表预览 */}
          <div style={styles.charts}>
            <h4>📈 图表预览</h4>
            <div style={styles.chartGrid}>
              {selectedReport.files.filter(f => f.type === 'chart').map((file, i) => (
                <div key={i} style={styles.chartCard}>
                  <h5>{file.name.replace('.png', '').replace('_', ' ')}</h5>
                  <img 
                    src={`${REPORTS_API_BASE}/reports/${file.name}`} 
                    alt={file.name}
                    style={styles.chartImage}
                  />
                  <button 
                    style={styles.downloadBtn}
                    onClick={() => handleDownload({file: file.name})}
                  >
                    下载原图
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* 数据文件 */}
          <div style={styles.dataFiles}>
            <h4>📁 数据文件</h4>
            {selectedReport.files.filter(f => f.type === 'data').map((file, i) => (
              <div key={i} style={styles.dataFile}>
                <span>{file.name}</span>
                <button 
                  style={styles.downloadBtn}
                  onClick={() => handleDownload({file: file.name})}
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

const styles = {
  container: {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto'
  },
  title: {
    fontSize: '24px',
    fontWeight: 'bold',
    marginBottom: '20px',
    color: '#333'
  },
  loading: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '400px',
    fontSize: '16px',
    color: '#666'
  },
  empty: {
    textAlign: 'center',
    padding: '60px 20px',
    color: '#666'
  },
  code: {
    display: 'block',
    marginTop: '20px',
    padding: '10px',
    background: '#f5f5f5',
    borderRadius: '4px',
    fontFamily: 'monospace'
  },
  reportList: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '20px',
    marginBottom: '30px'
  },
  reportCard: {
    padding: '20px',
    background: 'white',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    cursor: 'pointer',
    transition: 'all 0.3s'
  },
  reportCardSelected: {
    boxShadow: '0 4px 12px rgba(66, 153, 225, 0.5)',
    border: '2px solid #4299e1'
  },
  reportName: {
    fontSize: '18px',
    fontWeight: 'bold',
    marginBottom: '8px',
    color: '#2d3748'
  },
  reportDate: {
    fontSize: '14px',
    color: '#718096',
    marginBottom: '12px'
  },
  reportFiles: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap'
  },
  fileTag: {
    padding: '4px 8px',
    background: '#ebf8ff',
    color: '#3182ce',
    borderRadius: '4px',
    fontSize: '12px'
  },
  detail: {
    background: 'white',
    borderRadius: '8px',
    padding: '24px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
  },
  section: {
    marginBottom: '30px'
  },
  iframe: {
    width: '100%',
    height: '600px',
    border: '1px solid #e2e8f0',
    borderRadius: '4px'
  },
  summaryBox: {
    padding: '16px',
    background: '#f7fafc',
    borderRadius: '8px',
    border: '1px solid #e2e8f0'
  },
  summaryHint: {
    fontSize: '14px',
    color: '#4a5568',
    marginBottom: '12px'
  },
  charts: {
    marginBottom: '30px'
  },
  chartGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))',
    gap: '20px'
  },
  chartCard: {
    padding: '16px',
    background: '#f7fafc',
    borderRadius: '8px',
    textAlign: 'center'
  },
  chartImage: {
    width: '100%',
    height: 'auto',
    borderRadius: '4px',
    marginBottom: '12px'
  },
  downloadBtn: {
    padding: '8px 16px',
    background: '#4299e1',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px'
  },
  dataFiles: {
    borderTop: '1px solid #e2e8f0',
    paddingTop: '20px'
  },
  dataFile: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px',
    background: '#f7fafc',
    borderRadius: '4px',
    marginBottom: '8px'
  }
}

export default ReportsPage
