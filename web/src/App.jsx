import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell } from 'recharts'

const loadData = () => {
  return fetch('/ranking.json')
    .then(res => res.json())
    .then(data => ({
      ranking: data.ranking || [],
      factorWeights: data.factor_weights || {},
      strategy: data.strategy || {},
      updateTime: data.update_time || '',
      flowDetails: data.flow_details || {}  // 资金流子因子详情
    }))
    .catch(err => {
      console.error('加载失败:', err)
      return null
    })
}

const loadBacktestData = () => {
  return fetch('/backtest.json')
    .then(res => res.json())
    .then(data => ({
      summary: data.summary || {},
      chart_data: data.chart_data || []
    }))
    .catch(err => {
      console.error('加载失败:', err)
      return null
    })
}

const defaultFactorWeights = {
  momentum: 0.20,
  volatility: 0.15,
  trend: 0.20,
  value: 0.25,
  flow: 0.15,
  relative_strength: 0.20
}

const factorNames = {
  momentum: '动量',
  volatility: '波动',
  trend: '趋势',
  value: '估值',
  relative_strength: '强弱',
  flow: '资金流',
  fundamental: '基本面',
  sentiment: '情绪'
}

const factorDescriptions = {
  momentum: '6 个月收益率',
  volatility: '年化波动率 (低波高分)',
  trend: '价格相对 MA20/MA60 位置',
  value: '近 3 年价格分位 (低估高分)',
  relative_strength: '相对沪深 300 表现',
  flow: '资金流 (成交量 + 北向资金+ETF 份额)',
  fundamental: '基本面评分',
  sentiment: '市场情绪指标'
}

// 资金流子因子详情
const flowSubFactors = {
  volume_trend: { name: '成交量趋势', desc: '近 20 日 vs 前 20 日成交量变化' },
  price_volume_corr: { name: '量价配合', desc: '价格与成交量相关性' },
  amount_trend: { name: '金额趋势', desc: '成交金额变化趋势' },
  flow_intensity: { name: '流入强度', desc: '放量天数占比' },
  northbound: { name: '北向资金', desc: '沪深股通净买入趋势' },
  etf_shares: { name: 'ETF 份额', desc: '基金份额申购/赎回' }
}

function App() {
  const [data, setData] = useState(null)
  const [backtestData, setBacktestData] = useState(null)
  const [selectedCode, setSelectedCode] = useState('000933.CSI')
  const [showLogic, setShowLogic] = useState(false)
  const [tab, setTab] = useState('overview')
  const [showFlowDetail, setShowFlowDetail] = useState(false)
  const [aiSummary, setAiSummary] = useState(null)
  const [loadingSummary, setLoadingSummary] = useState(false)

  // 因子得分单元格组件
  const FactorCell = ({ value }) => {
    const safeVal = (value === null || value === undefined || (typeof value === 'number' && isNaN(value))) ? 0.5 : Number(value)
    const color = safeVal >= 0.7 ? 'text-emerald-400' : safeVal >= 0.5 ? 'text-gray-300' : 'text-red-400'
    const bg = safeVal >= 0.7 ? 'bg-emerald-500/20' : safeVal >= 0.5 ? 'bg-zinc-700' : 'bg-red-500/20'
    
    return (
      <div className="flex items-center gap-1">
        <span className={`font-mono text-xs ${color}`}>{safeVal.toFixed(2)}</span>
        <div className="w-8 h-1 bg-zinc-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${bg}`} style={{ width: `${safeVal * 100}%` }} />
        </div>
      </div>
    )
  }

  // 因子迷你展示组件（移动端）
  const FactorMini = ({ label, value }) => {
    const safeVal = (value === null || value === undefined || (typeof value === 'number' && isNaN(value))) ? 0.5 : Number(value)
    const color = safeVal >= 0.7 ? 'text-emerald-400' : safeVal >= 0.5 ? 'text-gray-400' : 'text-red-400'
    
    return (
      <div className="text-center">
        <div className="text-[10px] text-gray-600">{label}</div>
        <div className={`text-xs font-mono ${color}`}>{safeVal.toFixed(1)}</div>
      </div>
    )
  }

  // 生成 AI 深度分析总结（含归因和建议）
  const generateAiSummary = async () => {
    if (!selected || !selectedFactors) return
    
    setLoadingSummary(true)
    try {
      // 准备因子数据
      const factorData = factorKeys.map(key => ({
        key,
        name: factorNames[key] || key,
        score: safeNum(selectedFactors[key], 0.5),
        weight: safeNum(weights[key], 0) * 100
      }))
      
      // 获取归因数据
      const attribution = selected.attribution || {}
      
      const summary = {
        topFactor: factorData.reduce((a, b) => a.score > b.score ? a : b),
        weakFactor: factorData.reduce((a, b) => a.score < b.score ? a : b),
        avgScore: factorData.reduce((sum, f) => sum + f.score, 0) / factorData.length,
        totalScore: selected.score,
        attribution
      }
      
      // 生成深度分析
      const analysis = generateDeepAnalysis(summary, factorData, selectedName, selected.code)
      setAiSummary(analysis)
    } catch (err) {
      console.error('生成分析失败:', err)
      setAiSummary({ text: '分析生成失败，请稍后重试。', suggestions: [] })
    }
    setLoadingSummary(false)
  }

  // 生成深度分析文本（含归因和建议）
  const generateDeepAnalysis = (summary, factors, name, code) => {
    const { attribution, topFactor, weakFactor, avgScore, totalScore } = summary
    
    // ===== 第一部分：总体评价 =====
    let analysis = ''
    
    if (totalScore >= 0.75) {
      analysis += `${name}综合得分${(totalScore * 100).toFixed(0)}分，处于强势区间。`
    } else if (totalScore >= 0.6) {
      analysis += `${name}综合得分${(totalScore * 100).toFixed(0)}分，整体表现中等偏上。`
    } else if (totalScore >= 0.45) {
      analysis += `${name}综合得分${(totalScore * 100).toFixed(0)}分，整体表现中等。`
    } else {
      analysis += `${name}综合得分${(totalScore * 100).toFixed(0)}分，整体表现偏弱。`
    }
    
    // ===== 第二部分：因子归因 =====
    // 动量归因
    if (factors.find(f => f.key === 'momentum')) {
      const mom = factors.find(f => f.key === 'momentum')
      const mom60d = attribution.momentum_6m_return || 0
      const mom1m = attribution.momentum_1m_return || 0
      
      if (mom.score >= 0.7) {
        analysis += `动量因子强势（${(mom.score * 100).toFixed(0)}分），近 6 个月上涨${mom60d.toFixed(1)}%，近 1 个月上涨${mom1m.toFixed(1)}%，趋势延续性好。`
      } else if (mom.score <= 0.3) {
        analysis += `动量因子弱势（${(mom.score * 100).toFixed(0)}分），近 6 个月下跌${Math.abs(mom60d).toFixed(1)}%，短期动能不足。`
      }
    }
    
    // 波动归因
    if (factors.find(f => f.key === 'volatility')) {
      const vol = factors.find(f => f.key === 'volatility')
      const volAnn = attribution.volatility_annual || 0
      
      if (vol.score >= 0.7) {
        analysis += `波动率低（${volAnn.toFixed(1)}%），走势平稳，适合稳健配置。`
      } else if (vol.score <= 0.3) {
        analysis += `波动率高（${volAnn.toFixed(1)}%），价格波动剧烈，需注意风险控制。`
      }
    }
    
    // 趋势归因
    if (factors.find(f => f.key === 'trend')) {
      const trend = factors.find(f => f.key === 'trend')
      const vsMa20 = attribution.price_vs_ma20 || 0
      const vsMa60 = attribution.price_vs_ma60 || 0
      const maGolden = attribution.ma20_above_ma60
      
      if (trend.score >= 0.7) {
        analysis += `趋势向好，价格位于 MA20 上方${vsMa20.toFixed(1)}%、MA60 上方${vsMa60.toFixed(1)}%，${maGolden ? '均线呈多头排列' : '均线正在修复'}。`
      } else if (trend.score <= 0.3) {
        analysis += `趋势偏弱，价格低于 MA20 ${Math.abs(vsMa20).toFixed(1)}%、MA60 ${Math.abs(vsMa60).toFixed(1)}%，${maGolden ? '但均线仍为多头' : '均线呈空头排列'}。`
      }
    }
    
    // 估值归因
    if (factors.find(f => f.key === 'value')) {
      const val = factors.find(f => f.key === 'value')
      const percentile = attribution.value_percentile || 50
      const assessment = attribution.value_assessment || '合理'
      
      if (val.score >= 0.7) {
        analysis += `估值处于历史低位（分位${percentile.toFixed(0)}%，${assessment}），安全边际较高。`
      } else if (val.score <= 0.3) {
        analysis += `估值处于历史高位（分位${percentile.toFixed(0)}%，${assessment}），需注意回调风险。`
      } else {
        analysis += `估值处于合理区间（分位${percentile.toFixed(0)}%）。`
      }
    }
    
    // 相对强弱归因
    if (factors.find(f => f.key === 'relative_strength')) {
      const rs = factors.find(f => f.key === 'relative_strength')
      const excessReturn = attribution.relative_return || 0
      const idxReturn = attribution.index_return || 0
      const benchReturn = attribution.benchmark_return || 0
      const lookback = attribution.rs_lookback_days || 60
      
      if (rs.score >= 0.7) {
        analysis += `相对沪深 300 超额收益${excessReturn.toFixed(1)}%（${lookback}日，指数${idxReturn.toFixed(1)}% vs 基准${benchReturn.toFixed(1)}%），表现强势。`
      } else if (rs.score >= 0.55) {
        analysis += `相对沪深 300 超额收益${excessReturn.toFixed(1)}%（${lookback}日），小幅跑赢基准。`
      } else if (rs.score <= 0.3) {
        analysis += `相对沪深 300 落后${Math.abs(excessReturn).toFixed(1)}%（${lookback}日，指数${idxReturn.toFixed(1)}% vs 基准${benchReturn.toFixed(1)}%），表现弱势。`
      } else {
        analysis += `相对沪深 300 超额收益${excessReturn.toFixed(1)}%（${lookback}日），与基准持平。`
      }
    }
    
    // 资金流归因
    if (factors.find(f => f.key === 'flow')) {
      const flow = factors.find(f => f.key === 'flow')
      const nbSum = attribution.northbound_20d_sum || 0
      const nbTrend = attribution.northbound_trend || '未知'
      const etfChange = attribution.etf_shares_20d_change || 0
      const etfTrend = attribution.etf_shares_trend || '未知'
      
      if (flow.score >= 0.7) {
        analysis += `资金面积极：北向资金 20 日净流入${nbSum.toFixed(1)}亿（${nbTrend}），ETF 份额 20 日增长${etfChange.toFixed(1)}%（${etfTrend}）。`
      } else if (flow.score <= 0.3) {
        analysis += `资金面承压：北向资金 20 日净流出${Math.abs(nbSum).toFixed(1)}亿（${nbTrend}），ETF 份额 20 日变化${etfChange.toFixed(1)}%（${etfTrend}）。`
      }
    }
    
    // ===== 第三部分：投资建议 =====
    const suggestions = []
    
    if (totalScore >= 0.7) {
      suggestions.push({
        action: '建议超配',
        reason: '综合得分高，各因子表现良好',
        weight: '可配置目标权重的 120-150%'
      })
      
      if (attribution.value_percentile && attribution.value_percentile < 30) {
        suggestions.push({
          action: '逢低加仓',
          reason: '估值处于历史低位，安全边际高',
          weight: '分批建仓，避免追高'
        })
      }
    } else if (totalScore >= 0.5) {
      suggestions.push({
        action: '标配持有',
        reason: '综合得分中等，保持基准配置',
        weight: '维持目标权重'
      })
      
      if (attribution.price_vs_ma20 < -5) {
        suggestions.push({
          action: '关注反弹',
          reason: '价格偏离 MA20 较多，可能有技术性反弹',
          weight: '等待趋势确认'
        })
      }
    } else {
      suggestions.push({
        action: '低配或观望',
        reason: '综合得分偏低，多个因子表现弱势',
        weight: '降至目标权重的 50% 以下'
      })
      
      if (attribution.value_percentile && attribution.value_percentile > 70) {
        suggestions.push({
          action: '考虑减仓',
          reason: '估值处于历史高位，回调风险较大',
          weight: '逢高减持'
        })
      }
    }
    
    // 弱势因子改进建议
    if (weakFactor.score < 0.4) {
      if (weakFactor.key === 'momentum') {
        suggestions.push({
          action: '关注动量拐点',
          reason: '动量因子弱势，等待趋势反转信号',
          weight: '结合成交量和技术面判断'
        })
      } else if (weakFactor.key === 'volatility') {
        suggestions.push({
          action: '控制仓位',
          reason: '波动率过高，价格波动剧烈',
          weight: '降低单品种风险敞口'
        })
      } else if (weakFactor.key === 'trend') {
        suggestions.push({
          action: '等待趋势确认',
          reason: '趋势因子弱势，均线系统未走好',
          weight: '关注 MA20/MA60 金叉信号'
        })
      }
    }
    
    return { text: analysis, suggestions }
  }

  useEffect(() => {
    loadData().then(setData)
    loadBacktestData().then(setBacktestData)
  }, [])

  // 切换标的或切换到因子 tab 时生成分析
  useEffect(() => {
    if (tab === 'factors' && selected && !aiSummary && !loadingSummary) {
      generateAiSummary()
    }
  }, [tab, selectedCode])

  if (!data) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-white border-r-transparent" />
          <p className="mt-4 text-sm text-gray-400">Loading...</p>
        </div>
      </div>
    )
  }

  const { ranking, factorWeights, strategy, updateTime } = data
  const selected = ranking.find(d => d.code === selectedCode)
  const selectedName = selected?.name || selectedCode
  const selectedFactors = selected?.factors || {}
  
  // 使用 factors 的实际 key（而不是 weights），避免不匹配
  const factorKeys = selectedFactors && Object.keys(selectedFactors).length > 0 
    ? Object.keys(selectedFactors) 
    : Object.keys(defaultFactorWeights)

  const weights = factorWeights && Object.keys(factorWeights).length > 0 ? factorWeights : defaultFactorWeights

  // 辅助函数：安全获取数值（处理 NaN/null/undefined）
  const safeNum = (val, fallback = 0) => {
    if (val === null || val === undefined) return fallback
    const num = Number(val)
    return isNaN(num) ? fallback : num
  }

  const radarData = factorKeys.map(key => ({
    factor: factorNames[key] || key,
    score: safeNum(selectedFactors[key], 0.5),
    fullMark: 1
  }))

  const contributionData = factorKeys.map(key => ({
    name: factorNames[key] || key,
    score: safeNum(selectedFactors[key], 0.5),
    weight: safeNum(weights[key], 0) * 100
  }))

  const StatCard = ({ label, value, sub, positive }) => (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-bold ${positive === true ? 'text-emerald-400' : positive === false ? 'text-red-400' : 'text-white'}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )

  return (
    <div className="min-h-screen bg-black text-white pb-20">
      {/* Header */}
      <header className="border-b border-zinc-800 sticky top-0 bg-black/80 backdrop-blur z-40">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold">指数轮动策略</h1>
              <p className="text-xs text-gray-500 mt-0.5">{updateTime || '2026-03-17'}</p>
            </div>
            <div className="flex gap-1">
              {['overview', 'factors', 'backtest'].map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    tab === t ? 'bg-white text-black' : 'text-gray-400 hover:text-white hover:bg-zinc-900'
                  }`}
                >
                  {t === 'overview' ? '排名' : t === 'factors' ? '因子' : '回测'}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Overview Tab */}
        {tab === 'overview' && (
          <>
            {/* Ranking */}
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                指数排名（共 {ranking.length} 只）
              </h2>
              
              {/* Desktop Table */}
              <div className="hidden md:block bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">#</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">代码</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">名称</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">ETF</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">得分</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">动量</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">波动</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">趋势</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">估值</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">强弱</th>
                      <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">资金流</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranking.map((item, i) => (
                      <tr
                        key={item.code}
                        onClick={() => setSelectedCode(item.code)}
                        className={`border-b border-zinc-800 last:border-0 cursor-pointer transition-colors ${
                          selectedCode === item.code ? 'bg-zinc-800' : 'hover:bg-zinc-800/50'
                        }`}
                      >
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center justify-center w-5 h-5 rounded text-xs font-bold ${
                            item.rank <= 3 ? 'bg-amber-500/20 text-amber-400' : 'text-gray-500'
                          }`}>{item.rank}</span>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">{item.code}</td>
                        <td className="px-4 py-3">{item.name}</td>
                        <td className="px-4 py-3">
                          <span className="text-xs bg-zinc-800 px-2 py-0.5 rounded">{item.etf}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs">{item.score.toFixed(3)}</span>
                            <div className="w-16 h-1 bg-zinc-800 rounded-full overflow-hidden">
                              <div className="h-full bg-white rounded-full" style={{ width: `${item.score * 100}%` }} />
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <FactorCell value={item.factors?.momentum} />
                        </td>
                        <td className="px-4 py-3">
                          <FactorCell value={item.factors?.volatility} />
                        </td>
                        <td className="px-4 py-3">
                          <FactorCell value={item.factors?.trend} />
                        </td>
                        <td className="px-4 py-3">
                          <FactorCell value={item.factors?.value} />
                        </td>
                        <td className="px-4 py-3">
                          <FactorCell value={item.factors?.relative_strength} />
                        </td>
                        <td className="px-4 py-3">
                          <FactorCell value={item.factors?.flow} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Cards */}
              <div className="md:hidden space-y-2">
                {ranking.map((item) => (
                  <div
                    key={item.code}
                    onClick={() => setSelectedCode(item.code)}
                    className={`bg-zinc-900 border rounded-lg p-3 cursor-pointer transition-colors ${
                      selectedCode === item.code ? 'border-white' : 'border-zinc-800'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`w-5 h-5 rounded flex items-center justify-center text-xs font-bold ${
                          item.rank <= 3 ? 'bg-amber-500/20 text-amber-400' : 'bg-zinc-800 text-gray-500'
                        }`}>{item.rank}</span>
                        <span className="font-medium text-sm">{item.name}</span>
                      </div>
                      <span className="font-mono text-sm font-bold">{item.score.toFixed(3)}</span>
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs text-gray-500">{item.code}</span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs bg-zinc-800 px-1.5 py-0.5 rounded">{item.etf}</span>
                    </div>
                    {/* 因子迷你展示 */}
                    <div className="grid grid-cols-6 gap-1 mt-2">
                      <FactorMini label="动量" value={item.factors?.momentum} />
                      <FactorMini label="波动" value={item.factors?.volatility} />
                      <FactorMini label="趋势" value={item.factors?.trend} />
                      <FactorMini label="估值" value={item.factors?.value} />
                      <FactorMini label="强弱" value={item.factors?.relative_strength} />
                      <FactorMini label="资金" value={item.factors?.flow} />
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Selected Factor Summary */}
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                {selectedName} · 因子得分
              </h2>
              <div className="grid grid-cols-5 gap-2">
                {Object.entries(weights).map(([key, weight]) => {
                  const val = selectedFactors[key]
                  const safeVal = (val === null || val === undefined || (typeof val === 'number' && isNaN(val))) ? 0.5 : Number(val)
                  return (
                    <div key={key} className="bg-zinc-900 border border-zinc-800 rounded-lg p-2 text-center">
                      <div className="text-xs text-gray-500 mb-1">{factorNames[key]}</div>
                      <div className="text-sm font-bold">{safeVal.toFixed(2)}</div>
                      <div className="text-xs text-gray-600">{(weight * 100).toFixed(0)}%</div>
                    </div>
                  )
                })}
              </div>
            </section>
          </>
        )}

        {/* Factors Tab */}
        {tab === 'factors' && (
          <>
            {/* AI 深度分析 */}
            <section className="bg-gradient-to-r from-violet-900/20 to-purple-900/20 border border-violet-800/30 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <div className="text-xl">✨</div>
                <div className="flex-1 space-y-3">
                  <div className="text-xs text-violet-400 font-medium">AI 深度分析</div>
                  {loadingSummary ? (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-violet-400 border-r-transparent" />
                      正在分析因子归因...
                    </div>
                  ) : aiSummary ? (
                    <>
                      <p className="text-sm text-gray-300 leading-relaxed">{aiSummary.text}</p>
                      
                      {aiSummary.suggestions && aiSummary.suggestions.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-violet-800/30">
                          <div className="text-xs text-violet-400 font-medium mb-2">💡 投资建议</div>
                          <div className="space-y-2">
                            {aiSummary.suggestions.map((sug, i) => (
                              <div key={i} className="flex items-start gap-2 text-xs">
                                <span className="text-violet-400 mt-0.5">•</span>
                                <div>
                                  <span className="text-emerald-400 font-medium">{sug.action}</span>
                                  <span className="text-gray-400"> — {sug.reason}</span>
                                  {sug.weight && <span className="text-gray-500 block mt-0.5">({sug.weight})</span>}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <button
                      onClick={generateAiSummary}
                      className="text-xs text-violet-400 hover:text-violet-300"
                    >
                      点击生成深度分析 →
                    </button>
                  )}
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                {selectedName} · 因子分析
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Radar */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                  <h3 className="text-xs text-gray-500 mb-2">雷达图</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="#333" />
                      <PolarAngleAxis dataKey="factor" tick={{ fill: '#666', fontSize: 11 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fill: '#666', fontSize: 10 }} />
                      <Radar name="得分" dataKey="score" stroke="#fff" fill="#fff" fillOpacity={0.2} />
                      <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', fontSize: 11 }} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                {/* Bar */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                  <h3 className="text-xs text-gray-500 mb-2">得分对比</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={contributionData} layout="vertical" margin={{ left: 40 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                      <XAxis type="number" domain={[0, 1]} tick={{ fill: '#666', fontSize: 10 }} />
                      <YAxis dataKey="name" type="category" tick={{ fill: '#999', fontSize: 10 }} width={35} />
                      <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', fontSize: 11 }} />
                      <Bar dataKey="score" fill="#fff" radius={[0, 2, 2, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </section>

            {/* 资金流因子详情 */}
            {selectedFactors.flow !== undefined && (
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    资金流因子详解
                  </h2>
                  <button
                    onClick={() => setShowFlowDetail(!showFlowDetail)}
                    className="text-xs text-gray-500 hover:text-white"
                  >
                    {showFlowDetail ? '收起 ▲' : '展开 ▼'}
                  </button>
                </div>
                
                {showFlowDetail && (
                  <div className="space-y-4">
                    {/* 资金流子因子得分 */}
                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                      <h3 className="text-xs text-gray-500 mb-3">子因子得分</h3>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {Object.entries(flowSubFactors).map(([key, info]) => {
                          // 尝试从 flow_details 获取数据
                          const flowDetail = data.flowDetails?.[selectedCode] || {}
                          const subScore = flowDetail[key] !== undefined ? flowDetail[key] : 0.5
                          const safeScore = (typeof subScore === 'number' && isNaN(subScore)) ? 0.5 : Number(subScore)
                          
                          return (
                            <div key={key} className="bg-black/50 rounded p-2">
                              <div className="text-xs text-gray-500 mb-1">{info.name}</div>
                              <div className="text-sm font-bold">{safeScore.toFixed(2)}</div>
                              <div className="text-xs text-gray-600 mt-0.5">{info.desc}</div>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* 资金流权重分布 */}
                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                      <h3 className="text-xs text-gray-500 mb-3">权重分布</h3>
                      <ResponsiveContainer width="100%" height={180}>
                        <PieChart>
                          <Pie
                            data={[
                              { name: '基础指标', value: 60, color: '#3b82f6' },
                              { name: '北向资金', value: 20, color: '#10b981' },
                              { name: 'ETF 份额', value: 20, color: '#8b5cf6' }
                            ]}
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={60}
                            paddingAngle={2}
                            dataKey="value"
                          >
                            {[
                              { name: '基础指标', value: 60, color: '#3b82f6' },
                              { name: '北向资金', value: 20, color: '#10b981' },
                              { name: 'ETF 份额', value: 20, color: '#8b5cf6' }
                            ].map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', fontSize: 11 }} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="flex justify-center gap-4 mt-2 text-xs">
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                          <span className="text-gray-400">基础 60%</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                          <span className="text-gray-400">北向 20%</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-violet-500"></div>
                          <span className="text-gray-400">ETF 20%</span>
                        </div>
                      </div>
                    </div>

                    {/* 北向资金指标 */}
                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                      <h3 className="text-xs text-gray-500 mb-3">北向资金指标</h3>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {[
                          { label: '20 日净买入', key: 'net_flow_20d_sum', unit: '亿元' },
                          { label: '5 日均值', key: 'net_flow_5d_avg', unit: '亿元' },
                          { label: '买入占比', key: 'buy_ratio', unit: '%', percent: true },
                          { label: '趋势', key: 'trend', unit: '' }
                        ].map(metric => {
                          const flowDetail = data.flowDetails?.[selectedCode] || {}
                          const nbMetrics = flowDetail.northbound_metrics || {}
                          const value = nbMetrics[metric.key]
                          const displayValue = value !== undefined 
                            ? (metric.percent ? (value * 100).toFixed(0) : value.toFixed(2))
                            : '-'
                          const positive = value > 0
                          
                          return (
                            <div key={metric.key} className="bg-black/50 rounded p-2 text-center">
                              <div className="text-xs text-gray-500">{metric.label}</div>
                              <div className={`text-sm font-bold ${positive === true ? 'text-emerald-400' : positive === false ? 'text-red-400' : 'text-white'}`}>
                                {displayValue}{metric.unit}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* ETF 份额指标 */}
                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                      <h3 className="text-xs text-gray-500 mb-3">ETF 份额指标</h3>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {[
                          { label: '20 日变化', key: 'shares_change_20d', percent: true },
                          { label: '5 日变化', key: 'shares_change_5d', percent: true },
                          { label: '流入占比', key: 'inflow_days_ratio', percent: true },
                          { label: '趋势', key: 'trend', percent: true }
                        ].map(metric => {
                          const flowDetail = data.flowDetails?.[selectedCode] || {}
                          const etfMetrics = flowDetail.etf_shares_metrics || {}
                          const value = etfMetrics[metric.key]
                          const displayValue = value !== undefined ? (value * 100).toFixed(1) : '-'
                          const positive = value > 0
                          
                          return (
                            <div key={metric.key} className="bg-black/50 rounded p-2 text-center">
                              <div className="text-xs text-gray-500">{metric.label}</div>
                              <div className={`text-sm font-bold ${positive === true ? 'text-emerald-400' : positive === false ? 'text-red-400' : 'text-white'}`}>
                                {displayValue}%
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* Factor Logic */}
            <section className="bg-zinc-900 border border-zinc-800 rounded-lg">
              <button
                onClick={() => setShowLogic(!showLogic)}
                className="w-full px-4 py-3 flex items-center justify-between text-left"
              >
                <span className="text-sm font-medium">因子说明</span>
                <span className="text-xs text-gray-500">{showLogic ? '−' : '+'}</span>
              </button>
              {showLogic && (
                <div className="px-4 pb-4 space-y-3 border-t border-zinc-800 pt-3">
                  {/* 只显示实际存在的因子（同时有权重和得分） */}
                  {factorKeys
                    .filter(key => weights[key] !== undefined && selectedFactors[key] !== undefined)
                    .map((key) => {
                      const desc = factorDescriptions[key] || ''
                      const weight = weights[key] || 0
                      const score = selectedFactors[key] !== undefined ? selectedFactors[key] : 0.5
                      const safeScore = (typeof score === 'number' && isNaN(score)) ? 0.5 : Number(score)
                      
                      return (
                        <div key={key} className="flex justify-between items-start py-2 border-b border-zinc-800 last:border-0">
                          <div>
                            <div className="text-sm font-medium">{factorNames[key]}</div>
                            <div className="text-xs text-gray-500 mt-0.5">{desc}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-500">权重</div>
                            <div className="text-sm font-mono">{(weight * 100).toFixed(0)}%</div>
                            <div className="text-xs text-gray-500 mt-1">得分</div>
                            <div className="text-sm font-mono">{safeScore.toFixed(2)}</div>
                          </div>
                        </div>
                      )
                    })
                  }
                  <div className="pt-3 mt-3 border-t border-zinc-800">
                    <div className="text-xs text-gray-500 mb-2">综合得分计算</div>
                    <div className="bg-black rounded p-2 font-mono text-xs overflow-x-auto">
                      {factorKeys
                        .filter(key => weights[key] !== undefined && selectedFactors[key] !== undefined)
                        .map((key) => {
                          const weight = weights[key] || 0
                          const score = selectedFactors[key] !== undefined ? selectedFactors[key] : 0.5
                          const safeScore = (typeof score === 'number' && isNaN(score)) ? 0.5 : Number(score)
                          return (
                            <div key={key} className="flex justify-between py-0.5">
                              <span>{factorNames[key]}: {safeScore.toFixed(3)} × {weight.toFixed(2)}</span>
                              <span className="text-gray-500">{(safeScore * weight).toFixed(3)}</span>
                            </div>
                          )
                        })
                      }
                      <div className="border-t border-zinc-800 mt-2 pt-2 flex justify-between font-bold">
                        <span>总分</span>
                        <span>{selected?.score.toFixed(3)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </section>
          </>
        )}

        {/* Backtest Tab */}
        {tab === 'backtest' && backtestData && (
          <>
            {/* Stats Grid */}
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">回测摘要</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <StatCard
                  label="总收益"
                  value={`${(backtestData.summary.total_return * 100).toFixed(1)}%`}
                  positive={backtestData.summary.total_return >= 0}
                />
                <StatCard
                  label="年化"
                  value={`${(backtestData.summary.annual_return * 100).toFixed(1)}%`}
                  positive={backtestData.summary.annual_return >= 0}
                />
                <StatCard
                  label="最大回撤"
                  value={`${(backtestData.summary.max_drawdown * 100).toFixed(1)}%`}
                  positive={false}
                />
                <StatCard
                  label="夏普比率"
                  value={backtestData.summary.sharpe_ratio.toFixed(2)}
                  positive={backtestData.summary.sharpe_ratio >= 0}
                />
                <StatCard
                  label="初始"
                  value={`¥${(backtestData.summary.initial_capital / 10000).toFixed(0)}万`}
                />
                <StatCard
                  label="最终"
                  value={`¥${(backtestData.summary.final_value / 10000).toFixed(0)}万`}
                  positive={backtestData.summary.final_value >= backtestData.summary.initial_capital}
                />
                <StatCard
                  label="天数"
                  value={backtestData.summary.trading_days}
                />
                <StatCard
                  label="期间"
                  value={backtestData.summary.period?.start?.slice(5)}
                  sub={backtestData.summary.period?.end?.slice(5)}
                />
              </div>
            </section>

            {/* Charts */}
            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">净值曲线</h2>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={backtestData.chart_data}>
                    <defs>
                      <linearGradient id="gradValue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(v) => `${(v/10000).toFixed(0)}万`} />
                    <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', fontSize: 11 }} 
                      formatter={(v) => [`¥${(v/10000).toFixed(1)}万`, '净值']}
                      labelFormatter={(l) => `日期：${l}`}
                    />
                    <Area type="monotone" dataKey="value" stroke="#10b981" strokeWidth={2} fill="url(#gradValue)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">回撤分析</h2>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={backtestData.chart_data}>
                    <defs>
                      <linearGradient id="gradDD" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(v) => `${(v*100).toFixed(0)}%`} />
                    <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', fontSize: 11 }}
                      formatter={(v) => [`${(v*100).toFixed(1)}%`, '回撤']}
                      labelFormatter={(l) => `日期：${l}`}
                    />
                    <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={2} fill="url(#gradDD)" />
                  </AreaChart>
                </ResponsiveContainer>
                <div className="mt-2 text-xs text-gray-500">
                  最大回撤：{(backtestData.summary.max_drawdown * 100).toFixed(1)}%
                  {backtestData.summary.max_drawdown_date && ` · ${backtestData.summary.max_drawdown_date}`}
                </div>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">累计收益</h2>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={backtestData.chart_data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(v) => `${(v*100).toFixed(0)}%`} />
                    <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', fontSize: 11 }}
                      formatter={(v) => [`${(v*100).toFixed(1)}%`, '累计收益']}
                      labelFormatter={(l) => `日期：${l}`}
                    />
                    <Line type="monotone" dataKey="cum_return" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          </>
        )}

        {/* Strategy Info */}
        <section className="border-t border-zinc-800 pt-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs mb-6">
            <div>
              <div className="text-gray-500 mb-1">调仓频率</div>
              <div className="font-medium">{strategy?.rebalance_frequency === 'weekly' ? '每周一次' : '每月一次'}</div>
            </div>
            <div>
              <div className="text-gray-500 mb-1">配置规则</div>
              <div className="font-medium">前{strategy?.top_n || 5}名买入，跌出前{strategy?.buffer_n || 8}名卖出</div>
            </div>
            <div>
              <div className="text-gray-500 mb-1">交易成本</div>
              <div className="font-medium">佣金万三 · 滑点 0.1% · 现金 5%</div>
            </div>
          </div>

          {/* 监控指数列表 */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
              监控指数（共 {ranking.length} 只）
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {ranking.map((item) => (
                <div
                  key={item.code}
                  onClick={() => setSelectedCode(item.code)}
                  className={`p-2 rounded border cursor-pointer transition-colors ${
                    selectedCode === item.code
                      ? 'border-white bg-zinc-800'
                      : 'border-zinc-800 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium">{item.name}</span>
                    <span className={`text-[10px] px-1 rounded ${
                      item.rank <= 3 ? 'bg-amber-500/20 text-amber-400' : 'bg-zinc-800 text-gray-500'
                    }`}>#{item.rank}</span>
                  </div>
                  <div className="text-[10px] text-gray-500 font-mono">{item.code}</div>
                  <div className="text-[10px] text-gray-600 mt-0.5">{item.etf}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 py-6 text-center text-xs text-gray-600">
        数据仅供参考 · 不构成投资建议
      </footer>
    </div>
  )
}

export default App
