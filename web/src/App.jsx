import React, { useState, useEffect, useCallback, useMemo } from 'react'
import ErrorBoundary from './ErrorBoundary'
import OverviewPage from './pages/OverviewPage'
import FactorsPage from './pages/FactorsPage'
import BacktestPage from './pages/BacktestPage'
import ReportsPage from './pages/ReportsPage'
import { loadData, loadBacktestData, tabs, factorNames } from './utils'

function App() {
  const [data, setData] = useState(null)
  const [backtestData, setBacktestData] = useState(null)
  const [tab, setTab] = useState('overview')
  const [selectedCode, setSelectedCode] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadError, setLoadError] = useState(null)

  const refreshData = useCallback(async () => {
    setRefreshing(true)
    setLoadError(null)
    try {
      const [dataResult, backtestResult] = await Promise.all([loadData(), loadBacktestData()])
      setData(dataResult)
      setBacktestData(backtestResult)
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

  const handleSelectCode = useCallback((code) => setSelectedCode(code), [])

  // 加载状态
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

  // 加载错误
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

  // 无数据
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
      <div className="min-h-screen bg-zinc-950 text-zinc-50">
        <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-xl animate-fade-in">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Core Rotation</div>
              <h1 className="mt-1 text-xl font-semibold text-gradient">指数轮动决策面板</h1>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                <span>{data.updateTime}</span>
                <span className="text-zinc-700">·</span>
                <span>{data.marketRegimeDesc || data.marketRegime}</span>
                <span className="text-zinc-700">·</span>
                <span>模型：{data.factorModel?.baseline_name || 'core_rotation_v1'}</span>
              </div>
            </div>
            <div className="flex gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-1">
              {tabs.map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`rounded-lg px-3 py-1.5 text-sm transition-all duration-200 ${
                    tab === key ? 'bg-white text-zinc-950 shadow-lg' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              onClick={refreshData}
              disabled={refreshing}
              className={`absolute right-4 top-4 p-2 rounded-lg border border-zinc-700 transition-all duration-200 hover:bg-zinc-800 hover:scale-110 ${
                refreshing ? 'animate-spin' : ''
              }`}
              title="刷新数据"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </header>

        <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6">
          {tab === 'overview' && (
            <OverviewPage
              data={data}
              backtestData={backtestData}
              selectedCode={selectedCode}
              onSelectCode={(code) => { handleSelectCode(code); setTab('factors') }}
            />
          )}
          {tab === 'factors' && selected && (
            <FactorsPage
              data={data}
              selected={selected}
              activeFactors={activeFactors}
              auxFactors={auxFactors}
            />
          )}
          {tab === 'backtest' && <BacktestPage backtestData={backtestData} />}
          {tab === 'reports' && <ReportsPage />}
        </main>
      </div>
    </ErrorBoundary>
  )
}

export default App
