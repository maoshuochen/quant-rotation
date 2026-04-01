// 因子名称映射（仅活跃因子）
export const factorNames = {
  momentum: '动量',
  trend: '趋势',
  flow: '资金流'
}

// 安全数值转换
export const safeNum = (value, fallback = 0) => {
  if (value === null || value === undefined) return fallback
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

// 百分比格式化
export const pct = (value, digits = 1) => `${(safeNum(value) * 100).toFixed(digits)}%`

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

// 加载主数据
export const loadData = async () => {
  try {
    const res = await fetch('./ranking.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
    const data = await res.json()
    return {
      ranking: data.ranking || [],
      factorWeights: data.factor_weights || {},
      factorModel: data.factor_model || {},
      dynamicWeights: data.dynamic_weights || {},
      marketRegime: data.market_regime || 'sideways',
      marketRegimeDesc: data.market_regime_desc || '',
      strategy: data.strategy || {},
      updateTime: data.update_time || '',
      recommendation: data.recommendation || {},
      health: data.health || {},
      universe: data.universe || {}
    }
  } catch (err) {
    console.error('加载 ranking.json 失败:', err.message)
    return null
  }
}

// 加载回测数据
export const loadBacktestData = async () => {
  try {
    const res = await fetch('./backtest.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
    const data = await res.json()
    return {
      summary: data.summary || {},
      chartData: data.chart_data || []
    }
  } catch (err) {
    console.error('加载 backtest.json 失败:', err.message)
    return null
  }
}
