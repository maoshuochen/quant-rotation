import React, { useState, useEffect, useCallback, useMemo } from 'react'
import ErrorBoundary from './ErrorBoundary'
import Dashboard from './pages/Dashboard'
import { loadData, loadBacktestData, loadHistoryData } from './utils'

const THEME_KEY = 'qr-dashboard-theme'

const getInitialTheme = () => {
  if (typeof window === 'undefined') return 'dark'
  const saved = window.localStorage.getItem(THEME_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function App() {
  const [data, setData] = useState(null)
  const [backtestData, setBacktestData] = useState(null)
  const [historyData, setHistoryData] = useState(null)
  const [selectedCode, setSelectedCode] = useState(null)
  const [expandedSection, setExpandedSection] = useState('holdings')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [theme, setTheme] = useState(getInitialTheme)

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

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem(THEME_KEY, theme)
  }, [theme])

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

  const toggleTheme = useCallback(() => {
    setTheme((current) => current === 'dark' ? 'light' : 'dark')
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
      <div className={`app-shell min-h-screen ${theme === 'light' ? 'theme-light' : 'theme-dark'} bg-zinc-950 text-white`}>
        <Dashboard
          data={data}
          backtestData={backtestData}
          historyData={historyData}
          selected={selected}
          selectedCode={selectedCode}
          activeFactors={activeFactors}
          expandedSection={expandedSection}
          setExpandedSection={setExpandedSection}
          onSelectCode={handleSelectCode}
          refreshing={refreshing}
          onRefresh={refreshData}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
      </div>
    </ErrorBoundary>
  )
}

export default App
