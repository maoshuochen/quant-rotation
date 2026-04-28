// 因子名称映射
export const factorNames = {
  strength: '强度',
  momentum: '动量',
  trend: '趋势',
  flow: '资金流',
  relative_strength: '相对强弱',
  volatility: '低波动',
  value: '估值'
}

// 安全数值转换
export const safeNum = (value, fallback = 0) => {
  if (value === null || value === undefined) return fallback
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

// 百分比格式化
export const pct = (value, digits = 1) => `${(safeNum(value) * 100).toFixed(digits)}%`

export const dedupeHistoryByDate = (history = []) => {
  const seen = new Set()
  return history.filter((period) => {
    const date = period?.date
    if (!date || seen.has(date)) return false
    seen.add(date)
    return true
  })
}

// 健康状态文案
export const healthCopy = {
  ok: '数据完整，可直接执行',
  degraded: '部分数据降级，适合结合人工确认',
  snapshot: '份额数据为快照，可用于辅助判断',
  missing: '关键数据缺失，建议暂停执行'
}

// 健康状态样式
export const statusTone = {
  ok: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
  degraded: 'text-amber-200 border-amber-500/30 bg-amber-500/10',
  snapshot: 'text-sky-200 border-sky-500/30 bg-sky-500/10',
  missing: 'text-red-200 border-red-500/30 bg-red-500/10'
}

const fetchJson = async (path) => {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json()
}

const loadCombinedData = async () => fetchJson('./data.json')

// 加载历史数据
export const loadHistoryData = async () => {
  try {
    const data = await fetchJson('./history.json')
    return {
      history: data.history || [],
      updateTime: data.update_time || ''
    }
  } catch (err) {
    console.error('加载 history.json 失败，回退到 data.json:', err.message)
    try {
      const data = await loadCombinedData()
      return {
        history: data.history || [],
        updateTime: data.update_time || data.updateTime || ''
      }
    } catch (fallbackErr) {
      console.error('加载 data.json 失败:', fallbackErr.message)
      return null
    }
  }
}

// 加载主数据
export const loadData = async () => {
  try {
    const data = await fetchJson('./ranking.json')
    return {
      ranking: data.ranking || [],
      factorWeights: data.factor_weights || {},
      factorModel: data.factor_model || {},
      strategy: data.strategy || {},
      updateTime: data.update_time || '',
      recommendation: data.recommendation || {},
      health: data.health || {},
      universe: data.universe || {}
    }
  } catch (err) {
    console.error('加载 ranking.json 失败，回退到 data.json:', err.message)
    try {
      const data = await loadCombinedData()
      return {
        ranking: data.ranking || [],
        factorWeights: data.factor_weights || {},
        factorModel: data.factor_model || {},
        strategy: data.strategy || {},
        updateTime: data.update_time || data.updateTime || '',
        recommendation: data.recommendation || {},
        health: data.health || {},
        universe: data.universe || {}
      }
    } catch (fallbackErr) {
      console.error('加载 data.json 失败:', fallbackErr.message)
      return null
    }
  }
}

// 加载回测数据
export const loadBacktestData = async () => {
  try {
    const data = await fetchJson('./backtest.json')
    return {
      summary: data.summary || {},
      chartData: data.chart_data || [],
      metadata: data.metadata || {}
    }
  } catch (err) {
    console.error('加载 backtest.json 失败，回退到 data.json:', err.message)
    try {
      const data = await loadCombinedData()
      return {
        summary: data.backtest?.summary || {},
        chartData: data.backtest?.chart_data || [],
        metadata: data.backtest?.metadata || {}
      }
    } catch (fallbackErr) {
      console.error('加载 data.json 失败:', fallbackErr.message)
      return null
    }
  }
}
