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

  useEffect(() => {
    loadData().then(setData)
    loadBacktestData().then(setBacktestData)
  }, [])

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
              <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">指数排名</h2>
              
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
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">{item.code}</span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs bg-zinc-800 px-1.5 py-0.5 rounded">{item.etf}</span>
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
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
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
