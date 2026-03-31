import React, { useState } from 'react'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, BarChart, Bar } from 'recharts'
import { safeNum, pct, healthCopy, statusTone, factorNames } from '../utils'

const Card = ({ title, subtitle, children, className = '' }) => (
  <section className={`rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 ${className}`}>
    <div className="mb-4">
      <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
      {subtitle ? <p className="mt-1 text-sm text-zinc-500">{subtitle}</p> : null}
    </div>
    {children}
  </section>
)

const MetricCard = ({ label, value, sub, positive }) => (
  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
    <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
    <div className={`mt-2 text-xl font-semibold ${
      positive === true ? 'text-emerald-300' : positive === false ? 'text-red-300' : 'text-zinc-50'
    }`}>
      {value}
    </div>
    {sub ? <div className="mt-1 text-xs text-zinc-500">{sub}</div> : null}
  </div>
)

const HighlightStat = ({ label, value, detail, tone }) => (
  <div className={`rounded-2xl border p-4 ${
    tone === 'ok' ? 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10' :
    tone === 'degraded' ? 'text-amber-200 border-amber-500/30 bg-amber-500/10' :
    tone === 'snapshot' ? 'text-sky-200 border-sky-500/30 bg-sky-500/10' :
    tone === 'missing' ? 'text-red-200 border-red-500/30 bg-red-500/10' :
    'border-zinc-800 bg-zinc-900/60 text-zinc-50'
  }`}>
    <div className="text-xs uppercase tracking-wider opacity-80">{label}</div>
    <div className="mt-2 text-lg font-semibold">{value}</div>
    {detail ? <div className="mt-1 text-xs opacity-80">{detail}</div> : null}
  </div>
)

const SectionHeader = ({ id, title, subtitle, isActive, onClick }) => (
  <button
    onClick={onClick}
    className={`w-full text-left mb-4 transition-colors ${isActive ? 'opacity-100' : 'opacity-60 hover:opacity-100'}`}
  >
    <div className="flex items-center gap-3">
      <span className={`h-2 w-2 rounded-full ${isActive ? 'bg-amber-500' : 'bg-zinc-600'}`} />
      <h2 className="text-xl font-semibold text-zinc-100">{title}</h2>
    </div>
    {subtitle && <p className="mt-1 text-sm text-zinc-500 ml-5">{subtitle}</p>}
  </button>
)

const Dashboard = ({
  data,
  backtestData,
  selected,
  selectedCode,
  activeFactors,
  auxFactors,
  expandedSection,
  setExpandedSection,
  onSelectCode,
  refreshing,
  onRefresh
}) => {
  const [expandedCode, setExpandedCode] = useState(null)

  const recommendation = data?.recommendation || {}
  const health = data?.health || {}
  const universe = data?.universe || {}
  const holdings = recommendation.holdings || []
  const signals = recommendation.signals || []
  const backtestSummary = backtestData?.summary || {}
  const inactiveUniverse = universe.inactive || []

  const healthStates = [health.price_data?.status, health.northbound?.status, health.etf_shares?.status]
  const overallHealth =
    healthStates.includes('missing') ? 'missing' :
    healthStates.includes('degraded') ? 'degraded' :
    healthStates.includes('snapshot') ? 'snapshot' : 'ok'

  const topNames = holdings.slice(0, 3).map(item => item.name).join(', ')
  const executionHeadline = signals.length
    ? `当前建议执行 ${signals.length} 个动作，优先关注 ${topNames || '头部候选'}。`
    : `当前无新增调仓动作，继续跟踪 ${topNames || '头部候选'}。`

  const overviewHealth = [
    { label: '价格数据', value: health.price_data?.status || 'unknown', detail: `${health.price_data?.available_count || 0}/${health.price_data?.expected_count || 0}` },
    { label: '北向资金', value: health.northbound?.status || 'unknown', detail: health.northbound?.latest_valid_date ? `最近连续 ${health.northbound.recent_rows || 0} 日` : `${health.northbound?.rows || 0} 行` },
    { label: 'ETF 份额', value: health.etf_shares?.status || 'unknown', detail: `历史 ${health.etf_shares?.history_count || 0} / 快照 ${health.etf_shares?.snapshot_count || 0}` }
  ]

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  const toggleCodeExpand = (code) => {
    setExpandedCode(expandedCode === code ? null : code)
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Core Rotation</div>
            <h1 className="mt-1 text-xl font-semibold text-gradient">指数轮动决策面板</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
              <span className="text-zinc-300">{data.updateTime}</span>
              <span className="text-zinc-700">·</span>
              <span>{data.marketRegimeDesc || data.marketRegime}</span>
              <span className="text-zinc-700">·</span>
              <span>模型：{data.factorModel?.baseline_name || 'core_rotation_v1'}</span>
            </div>
          </div>
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className={`p-2 rounded-lg border border-zinc-700 transition-all duration-200 hover:bg-zinc-800 hover:scale-110 ${refreshing ? 'animate-spin' : ''}`}
            title="刷新数据"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </header>

      {/* Main Content - Single Page Scroll */}
      <main className="mx-auto max-w-7xl px-4 py-6 space-y-8">
        {/* Weekly Brief Hero */}
        <section className="overflow-hidden rounded-3xl border border-zinc-800 gradient-hero p-6 backdrop-blur-xl animate-fade-in">
          <div className="text-xs uppercase tracking-[0.28em] text-zinc-500">Weekly Decision Brief</div>
          <h2 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight text-gradient">
            本周主结论：{topNames || '等待新信号'} 仍是当前最值得优先配置的方向。
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-zinc-300">
            {executionHeadline} 当前市场处于
            <span className="mx-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-zinc-100">
              {data.marketRegimeDesc || data.marketRegime}
            </span>
            ，主模型只使用 {activeFactors.length} 个因子参与总分。
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {holdings.slice(0, 5).map((item, idx) => (
              <button
                key={item.code}
                onClick={() => onSelectCode(item.code)}
                className={`rounded-full border border-white/10 bg-white/5 px-3 py-2 text-zinc-100 transition hover:bg-white/10 hover:scale-105 active:scale-95 ${idx === 0 ? 'glow-amber' : ''}`}
              >
                {item.name} · {safeNum(item.score).toFixed(3)}
              </button>
            ))}
          </div>
        </section>

        {/* Quick Stats */}
        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <HighlightStat label="策略可信度" value={healthCopy[overallHealth] || '待确认'} tone={overallHealth} />
          <HighlightStat label="覆盖范围" value={`${health.universe?.active_count || data.ranking.length} 只`} detail={inactiveUniverse.length ? `${inactiveUniverse.length} 只已下线` : '全部活跃'} />
          <HighlightStat label="待执行信号" value={signals.length ? `${signals.length} 个` : '暂无'} detail={`最近更新 ${data.updateTime}`} />
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="text-xs uppercase tracking-wider text-zinc-500">回测收益</div>
            <div className={`mt-2 text-xl font-semibold ${safeNum(backtestSummary.total_return, 0) >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
              {backtestSummary.total_return !== undefined ? pct(backtestSummary.total_return) : '暂无'}
            </div>
            <div className="mt-1 text-xs text-zinc-500">最大回撤 {pct(backtestSummary.max_drawdown || 0)}</div>
          </div>
        </section>

        {/* Section 1: Holdings */}
        <div>
          <SectionHeader
            id="holdings"
            title="建议持仓"
            subtitle="优先回答&apos;现在该持有什么、为什么持有&apos;"
            isActive={expandedSection === 'holdings'}
            onClick={() => toggleSection('holdings')}
          />
          {(expandedSection === 'holdings' || expandedSection === null) && (
            <div className="grid gap-4 lg:grid-cols-3 animate-fade-in">
              {/* Holdings List */}
              <div className="lg:col-span-2 space-y-3">
                {holdings.map((item, idx) => (
                  <div key={item.code} className="rounded-xl border border-zinc-800 bg-zinc-900/70 transition-all duration-300 hover:border-zinc-700">
                    <div
                      className="flex items-center justify-between p-4 cursor-pointer"
                      onClick={() => toggleCodeExpand(item.code)}
                    >
                      <div className="flex items-center gap-3">
                        <span className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold text-white ${idx === 0 ? 'bg-amber-500' : idx === 1 ? 'bg-zinc-400' : idx === 2 ? 'bg-amber-700' : 'bg-white/10'}`}>
                          {item.rank}
                        </span>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-zinc-100">{item.name}</span>
                            <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{item.etf}</span>
                          </div>
                          <div className="text-xs text-zinc-500 mt-0.5">
                            强项：{item.strongest_factors?.map(key => factorNames[key] || key).join('、') || '-'}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-zinc-500">综合得分</div>
                        <div className="font-mono text-lg text-gradient">{safeNum(item.score).toFixed(3)}</div>
                      </div>
                    </div>
                    {expandedCode === item.code && (
                      <div className="border-t border-zinc-800 p-4 bg-zinc-950/50">
                        <div className="grid gap-4 md:grid-cols-2">
                          <div>
                            <div className="text-xs text-zinc-500 mb-2">因子得分</div>
                            <div className="space-y-2">
                              {activeFactors.map(key => (
                                <div key={key} className="flex items-center gap-2">
                                  <span className="text-xs text-zinc-400 w-16">{factorNames[key]}</span>
                                  <div className="flex-1 h-2 rounded-full bg-zinc-800">
                                    <div className="h-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-400" style={{ width: `${safeNum(item.factors?.[key], 0.5) * 100}%` }} />
                                  </div>
                                  <span className="text-xs font-mono text-zinc-300 w-8">{safeNum(item.factors?.[key], 0.5).toFixed(2)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-zinc-500 mb-2">关键归因</div>
                            <div className="space-y-1.5 text-xs">
                              <div className="flex justify-between"><span className="text-zinc-400">6 个月收益</span><span className="text-zinc-200">{safeNum(item.attribution?.momentum_6m_return, 0).toFixed(1)}%</span></div>
                              <div className="flex justify-between"><span className="text-zinc-400">相对沪深 300</span><span className="text-zinc-200">{safeNum(item.attribution?.relative_return, 0).toFixed(1)}%</span></div>
                              <div className="flex justify-between"><span className="text-zinc-400">北向 20 日</span><span className="text-zinc-200">{safeNum(item.attribution?.northbound_20d_sum, 0).toFixed(1)}亿</span></div>
                              <div className="flex justify-between"><span className="text-zinc-400">ETF 份额 20 日</span><span className="text-zinc-200">{safeNum(item.attribution?.etf_shares_20d_change, 0).toFixed(1)}%</span></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Execution Checklist */}
              <Card title="执行清单" subtitle="把策略输出转成可执行动作">
                <div className="space-y-3">
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                    <div className="text-xs uppercase tracking-wider text-zinc-500">调仓规则</div>
                    <div className="mt-1.5 text-sm text-zinc-200">
                      前 {recommendation.top_n || 0} 名买入，跌出前 {recommendation.buffer_n || 0} 名卖出，按{recommendation.rebalance_frequency === 'weekly' ? '周度' : '月度'}调仓。
                    </div>
                  </div>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                    <div className="text-xs uppercase tracking-wider text-zinc-500">本次信号</div>
                    <div className="mt-1.5 space-y-1.5">
                      {signals.length === 0 ? (
                        <div className="flex items-center gap-2 text-zinc-400 text-sm">
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          维持现有持仓
                        </div>
                      ) : (
                        signals.map((signal, index) => (
                          <div key={`${signal.code}-${index}`} className="flex items-center justify-between rounded-lg bg-zinc-950 px-2.5 py-1.5">
                            <span className="font-mono text-sm">{signal.code}</span>
                            <span className={`flex items-center gap-1 text-xs ${signal.action === 'buy' ? 'text-emerald-300' : 'text-red-300'}`}>
                              {signal.action === 'buy' ? '买入' : '卖出'}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </div>

        {/* Section 2: Health & Factors */}
        <div>
          <SectionHeader
            id="health"
            title="数据健康度 & 因子权重"
            subtitle="先看结果是否可信，再看模型如何决策"
            isActive={expandedSection === 'health'}
            onClick={() => toggleSection('health')}
          />
          {(expandedSection === 'health' || expandedSection === null) && (
            <div className="grid gap-4 lg:grid-cols-2 animate-fade-in">
              <Card title="数据健康度">
                <div className="grid gap-3 md:grid-cols-3">
                  {overviewHealth.map(item => (
                    <div key={item.label} className={`rounded-xl border p-3 ${statusTone[item.value] || 'border-zinc-700 bg-zinc-900 text-zinc-200'}`}>
                      <div className="text-xs uppercase tracking-wider opacity-80">{item.label}</div>
                      <div className="mt-1.5 text-base font-medium">{item.value}</div>
                      <div className="mt-0.5 text-xs opacity-80">{item.detail}</div>
                    </div>
                  ))}
                </div>
              </Card>
              <Card title="因子权重">
                <div className="space-y-2.5">
                  {Object.entries(data.factorWeights || {}).filter(([_, v]) => safeNum(v) > 0).map(([key, weight]) => (
                    <div key={key}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-zinc-300">{factorNames[key] || key}</span>
                        <span className="font-mono text-zinc-300">{(safeNum(weight) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-zinc-800">
                        <div className="h-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-400" style={{ width: `${safeNum(weight) * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </div>

        {/* Section 3: Full Ranking Table */}
        <div>
          <SectionHeader
            id="ranking"
            title="完整排名"
            subtitle="全部标的的横截面比较"
            isActive={expandedSection === 'ranking'}
            onClick={() => toggleSection('ranking')}
          />
          {(expandedSection === 'ranking' || expandedSection === null) && (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 animate-fade-in">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-zinc-500 border-b border-zinc-800">
                      <th className="px-3 py-3">#</th>
                      <th className="px-3 py-3">名称</th>
                      <th className="px-3 py-3">代码</th>
                      <th className="px-3 py-3">ETF</th>
                      <th className="px-3 py-3">总分</th>
                      {activeFactors.map(key => (
                        <th key={key} className="px-3 py-3">{factorNames[key]}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data?.ranking?.map(item => (
                      <tr
                        key={item.code}
                        className={`border-b border-zinc-900 hover:bg-zinc-900/80 ${selectedCode === item.code ? 'bg-zinc-900' : ''}`}
                        onClick={() => onSelectCode(item.code)}
                      >
                        <td className="px-3 py-3 font-mono text-zinc-400">{item.rank}</td>
                        <td className="px-3 py-3">{item.name}</td>
                        <td className="px-3 py-3 font-mono text-xs text-zinc-400">{item.code}</td>
                        <td className="px-3 py-3 text-zinc-400">{item.etf}</td>
                        <td className="px-3 py-3 font-mono">{safeNum(item.score).toFixed(3)}</td>
                        {activeFactors.map(key => (
                          <td key={key} className="px-3 py-3 font-mono text-zinc-300">
                            {safeNum(item.factors?.[key], 0.5).toFixed(2)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Section 4: Backtest */}
        <div>
          <SectionHeader
            id="backtest"
            title="回测分析"
            subtitle="历史表现参考，不作为未来承诺"
            isActive={expandedSection === 'backtest'}
            onClick={() => toggleSection('backtest')}
          />
          {(expandedSection === 'backtest' || expandedSection === null) && (
            <div className="animate-fade-in">
              {backtestData?.chartData?.length ? (
                <Card>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={backtestData.chartData}>
                      <defs>
                        <linearGradient id="colorReturn" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f87171" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#f87171" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} minTickGap={32} />
                      <YAxis tick={{ fill: '#71717a', fontSize: 10 }} />
                      <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
                      <Area type="monotone" dataKey="cum_return" stroke="#f59e0b" fill="url(#colorReturn)" strokeWidth={2} />
                      <Area type="monotone" dataKey="drawdown" stroke="#f87171" fill="url(#colorDrawdown)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>
              ) : (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-6 text-sm text-zinc-400 text-center">
                  尚未生成可用的回测图表数据
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default Dashboard
