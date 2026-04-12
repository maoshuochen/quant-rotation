import React, { useState, useEffect, useCallback, useMemo } from 'react'
import ErrorBoundary from './ErrorBoundary'
import Dashboard from './pages/Dashboard'
import HistoryPanel from './pages/HistoryPanel'
import { loadData, loadBacktestData, loadHistoryData } from './utils'

function App() {
  const [data, setData] = useState(null)
  const [backtestData, setBacktestData] = useState(null)
  const [historyData, setHistoryData] = useState(null)
  const [selectedCode, setSelectedCode] = useState(null)
  const [expandedSection, setExpandedSection] = useState('holdings')
  const [activeTab, setActiveTab] = useState('current')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadError, setLoadError] = useState(null)

  const refreshData = useCallback(async () => {
    setRefreshing(true)
    setLoadError(null)
    try {
      const [dataResult, backtestResult, historyResult] = await Promise.all([
        loadData(),
        loadBacktestData(),
        loadHistoryData()
      ])
      setData(dataResult)
      setBacktestData(backtestResult)
      setHistoryData(historyResult)
      if (dataResult?.recommendation?.selected_codes?.length) {
        setSelectedCode(dataResult.recommendation.selected_codes[0])
      } else if (dataResult?.ranking?.length) {
        setSelectedCode(dataResult.ranking[0].code)
      }
    } catch (err) {
      setLoadError(err.message || '加载失败')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { refreshData() }, [refreshData])

  const selected = useMemo(() => {
    if (!data?.ranking?.length) return null
    return data.ranking.find(item => item.code === selectedCode) || data.ranking[0]
  }, [data, selectedCode])

  const activeFactors = data?.factorModel?.active_factors || []
  const auxFactors = data?.factorModel?.auxiliary_factors || []

  const handleSelectCode = useCallback((code) => {
    setSelectedCode(code)
    setExpandedSection('factors')
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-7 w-7 animate-spin rounded-full border-2 border-white border-r-transparent" />
          <p className="mt-4 text-sm text-zinc-400">正在加载策略看板...</p>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">加载失败：{loadError}</p>
          <button onClick={refreshData} className="px-4 py-2 bg-white text-zinc-950 rounded-lg hover:bg-zinc-200 transition">重试</button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-zinc-400 mb-4">暂无数据</p>
          <button onClick={refreshData} className="px-4 py-2 bg-white text-zinc-950 rounded-lg hover:bg-zinc-200 transition">刷新</button>
        </div>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-zinc-950 text-white">
        {/* Tab Navigation */}
        <div className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-xl">
          <div className="mx-auto max-w-7xl px-3 sm:px-4">
            <div className="flex items-center gap-1 sm:gap-2">
              <button
                onClick={() => setActiveTab('current')}
                className={`px-3 sm:px-4 py-3 text-xs sm:text-sm font-medium transition-all border-b-2 ${
                  activeTab === 'current'
                    ? 'border-amber-500 text-amber-500'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                当前周期
              </button>
              <button
                onClick={() => setActiveTab('history')}
                className={`px-3 sm:px-4 py-3 text-xs sm:text-sm font-medium transition-all border-b-2 ${
                  activeTab === 'history'
                    ? 'border-amber-500 text-amber-500'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                历史周期
              </button>
            </div>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'current' ? (
          <Dashboard
            data={data}
            backtestData={backtestData}
            selected={selected}
            selectedCode={selectedCode}
            activeFactors={activeFactors}
            expandedSection={expandedSection}
            setExpandedSection={setExpandedSection}
            onSelectCode={handleSelectCode}
            refreshing={refreshing}
            onRefresh={refreshData}
          />
        ) : (
          <HistoryPanel
            historyData={historyData}
            activeFactors={activeFactors}
            selectedCode={selectedCode}
            onSelectCode={setSelectedCode}
          />
        )}
      </div>
    </ErrorBoundary>
  )
}

export default App
