import React, { useState, useEffect } from 'react'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import { safeNum, pct, healthCopy, statusTone, factorNames } from '../utils'

const Card = ({ title, subtitle, children, className = '' }) => (
  <section className={`rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 sm:p-5 ${className}`}>
    <div className="mb-4">
      <h2 className="text-base sm:text-lg font-semibold text-zinc-100">{title}</h2>
      {subtitle ? <p className="mt-1 text-xs sm:text-sm text-zinc-500">{subtitle}</p> : null}
    </div>
    {children}
  </section>
)

const HighlightStat = ({ label, value, detail, tone }) => (
  <div className={`rounded-2xl border p-3 sm:p-4 ${
    tone === 'ok' ? 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10' :
    tone === 'degraded' ? 'text-amber-200 border-amber-500/30 bg-amber-500/10' :
    tone === 'snapshot' ? 'text-sky-200 border-sky-500/30 bg-sky-500/10' :
    tone === 'missing' ? 'text-red-200 border-red-500/30 bg-red-500/10' :
    'border-zinc-800 bg-zinc-900/60 text-zinc-50'
  }`}>
    <div className="text-[10px] sm:text-xs uppercase tracking-wider opacity-80">{label}</div>
    <div className="mt-1.5 sm:mt-2 text-base sm:text-lg font-semibold">{value}</div>
    {detail ? <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-xs opacity-80">{detail}</div> : null}
  </div>
)

const SectionHeader = ({ title, subtitle, isExpanded, onClick }) => (
  <button
    onClick={onClick}
    className="w-full text-left mb-3 sm:mb-4 group"
    aria-expanded={isExpanded}
  >
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 sm:gap-3">
        <span className={`h-2 w-2 rounded-full transition-colors ${isExpanded ? 'bg-amber-500' : 'bg-zinc-600'}`} />
        <h2 className="text-base sm:text-xl font-semibold text-zinc-100">{title}</h2>
      </div>
      <svg
        className={`h-5 w-5 text-zinc-500 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </div>
    {subtitle && <p className="mt-1 text-xs sm:text-sm text-zinc-500 pl-5">{subtitle}</p>}
  </button>
)

// 从 ranking 中查找持仓的完整数据
const getHoldingDetail = (code, ranking) => {
  if (!ranking) return null
  return ranking.find(item => item.code === code) || null
}

const HoldingCard = ({ item, idx, rankingData, isExpanded, onToggle, activeFactors }) => {
  const score = safeNum(item.score).toFixed(3)
  // 从 ranking 中获取完整数据用于展开详情
  const detail = getHoldingDetail(item.code, rankingData)
  const factors = detail?.factors || item.factors || {}
  const attribution = detail?.attribution || item.attribution || {}

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 transition-all duration-300 hover:border-zinc-700">
      <div
        className="flex items-center justify-between p-3 sm:p-4 cursor-pointer active:bg-zinc-800/50"
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onToggle()}
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
          <span className={`flex-shrink-0 inline-flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-full text-xs sm:text-sm font-semibold text-white ${
            idx === 0 ? 'bg-amber-500' : idx === 1 ? 'bg-zinc-400' : idx === 2 ? 'bg-amber-700' : 'bg-white/10'
          }`}>
            {item.rank}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-medium text-zinc-100 truncate">{item.name}</span>
              <span className="flex-shrink-0 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] sm:text-xs text-zinc-400">{item.etf}</span>
            </div>
            <div className="text-[10px] sm:text-xs text-zinc-500 mt-0.5 truncate">
              强项：{item.strongest_factors?.map(key => factorNames[key] || key).slice(0, 2).join('、') || '-'}
            </div>
          </div>
        </div>
        <div className="flex-shrink-0 text-right ml-2">
          <div className="text-[10px] sm:text-xs text-zinc-500">得分</div>
          <div className="font-mono text-sm sm:text-lg text-gradient">{score}</div>
        </div>
      </div>

      {isExpanded && (
        <div className="border-t border-zinc-800 p-3 sm:p-4 bg-zinc-950/50 space-y-3">
          <div>
            <div className="text-[10px] text-zinc-500 mb-2">因子得分</div>
            <div className="space-y-1.5">
              {activeFactors.map(key => (
                <div key={key} className="flex items-center gap-2">
                  <span className="text-[10px] text-zinc-400 w-12 sm:w-16 flex-shrink-0">{factorNames[key]}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-zinc-800 min-w-0">
                    <div className="h-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-400" style={{ width: `${safeNum(factors[key], 0.5) * 100}%` }} />
                  </div>
                  <span className="text-[10px] font-mono text-zinc-300 w-8 flex-shrink-0 text-right">{safeNum(factors[key], 0.5).toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="pt-2 border-t border-zinc-800">
            <div className="text-[10px] text-zinc-500 mb-1.5">关键归因</div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1">
              <div className="flex justify-between text-[10px]"><span className="text-zinc-400">6 月收益</span><span className="text-zinc-200">{safeNum(attribution?.momentum_6m_return, 0).toFixed(1)}%</span></div>
              <div className="flex justify-between text-[10px]"><span className="text-zinc-400">相对沪深 300</span><span className="text-zinc-200">{safeNum(attribution?.relative_return, 0).toFixed(1)}%</span></div>
              <div className="flex justify-between text-[10px]"><span className="text-zinc-400">北向 20 日</span><span className="text-zinc-200">{safeNum(attribution?.northbound_20d_sum, 0).toFixed(1)}亿</span></div>
              <div className="flex justify-between text-[10px]"><span className="text-zinc-400">ETF 份额</span><span className="text-zinc-200">{safeNum(attribution?.etf_shares_20d_change, 0).toFixed(1)}%</span></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const RankingCard = ({ item, onSelect, isActive }) => (
  <div
    onClick={() => onSelect(item.code)}
    className={`rounded-xl border p-3 cursor-pointer transition-all ${
      isActive ? 'border-amber-500/50 bg-amber-500/5' : 'border-zinc-800 bg-zinc-900/70 hover:border-zinc-700'
    }`}
    role="button"
    tabIndex={0}
    onKeyDown={(e) => e.key === 'Enter' && onSelect(item.code)}
  >
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className={`flex-shrink-0 inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
          item.rank <= 3 ? 'bg-amber-500 text-white' : 'bg-zinc-800 text-zinc-400'
        }`}>
          {item.rank}
        </span>
        <div>
          <div className="font-medium text-zinc-100">{item.name}</div>
          <div className="text-[10px] text-zinc-500">{item.code}</div>
        </div>
      </div>
      <div className="font-mono text-sm text-gradient">{safeNum(item.score).toFixed(3)}</div>
    </div>
  </div>
)

const Dashboard = ({
  data,
  backtestData,
  selected,
  selectedCode,
  activeFactors,
  expandedSection,
  setExpandedSection,
  onSelectCode,
  refreshing,
  onRefresh
}) => {
  const [expandedCode, setExpandedCode] = useState(null)
  const [showScrollTop, setShowScrollTop] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setShowScrollTop(window.scrollY > 400)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const recommendation = data?.recommendation || {}
  const health = data?.health || {}
  const universe = data?.universe || {}
  const holdings = recommendation.holdings || []
  const signals = recommendation.signals || []
  const backtestSummary = backtestData?.summary || {}
  const inactiveUniverse = universe.inactive || []
  const ranking = data?.ranking || []

  const healthStates = [health.price_data?.status, health.northbound?.status, health.etf_shares?.status]
  const overallHealth =
    healthStates.includes('missing') ? 'missing' :
    healthStates.includes('degraded') ? 'degraded' :
    healthStates.includes('snapshot') ? 'snapshot' : 'ok'

  const topNames = holdings.slice(0, 3).map(item => item.name).join(', ')
  const executionHeadline = signals.length
    ? `建议执行 ${signals.length} 个动作，关注 ${topNames || '头部'}。`
    : `无新增动作，跟踪 ${topNames || '头部候选'}。`

  const overviewHealth = [
    { label: '价格数据', value: health.price_data?.status || 'unknown', detail: `${health.price_data?.available_count || 0}/${health.price_data?.expected_count || 0}` },
    { label: '北向资金', value: health.northbound?.status || 'unknown', detail: `${health.northbound.recent_rows || 0} 日` },
    { label: 'ETF 份额', value: health.etf_shares?.status || 'unknown', detail: `快照 ${health.etf_shares?.snapshot_count || 0}` }
  ]

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  const toggleCodeExpand = (code) => {
    setExpandedCode(expandedCode === code ? null : code)
  }

  const chartHeight = typeof window !== 'undefined' && window.innerWidth < 640 ? 220 : 300

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      {/* Mobile-optimized Header */}
      <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-3 sm:px-4 py-3 sm:py-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Core</span>
              <h1 className="text-sm sm:text-lg font-semibold text-gradient truncate">指数轮动</h1>
            </div>
            <div className="hidden sm:flex items-center gap-2 text-xs text-zinc-400 mt-1">
              <span>{data.updateTime}</span>
              <span className="text-zinc-700">·</span>
              <span>{data.marketRegimeDesc || data.marketRegime}</span>
            </div>
          </div>
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className={`flex-shrink-0 ml-2 p-2 rounded-lg border border-zinc-700 transition-all active:scale-95 ${refreshing ? 'animate-spin' : ''}`}
            title="刷新数据"
            aria-label="刷新数据"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
        {/* Mobile sub-header with metadata */}
        <div className="sm:hidden px-3 pb-2 pt-1 border-t border-zinc-800/50">
          <div className="flex items-center gap-2 text-[10px] text-zinc-400 overflow-x-auto whitespace-nowrap">
            <span className="text-zinc-300">{data.updateTime}</span>
            <span className="text-zinc-700">·</span>
            <span>{data.marketRegimeDesc || data.marketRegime}</span>
            <span className="text-zinc-700">·</span>
            <span>模型：{data.factorModel?.baseline_name || 'v1'}</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-3 sm:px-4 py-4 sm:py-6 space-y-4 sm:space-y-6 pb-20">
        {/* Weekly Brief Hero - Mobile Optimized */}
        <section className="overflow-hidden rounded-2xl sm:rounded-3xl border border-zinc-800 gradient-hero p-4 sm:p-6 backdrop-blur-xl">
          <div className="text-[10px] uppercase tracking-[0.25em] text-zinc-500">本周结论</div>
          <h2 className="mt-2 text-base sm:text-2xl font-semibold text-gradient leading-tight">
            {topNames || '等待新信号'}
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
            {executionHeadline}
            <span className="inline-block mx-1 px-1.5 py-0.5 rounded-full border border-white/10 bg-white/5 text-[10px] sm:text-xs">
              {data.marketRegimeDesc || data.marketRegime}
            </span>
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5 sm:gap-2">
            {holdings.slice(0, 5).map((item, idx) => (
              <button
                key={item.code}
                onClick={() => onSelectCode(item.code)}
                className="flex-shrink-0 rounded-full border border-white/10 bg-white/5 px-2.5 sm:px-3 py-1.5 text-[10px] sm:text-xs text-zinc-100 transition active:scale-95"
              >
                {item.name} {safeNum(item.score).toFixed(2)}
              </button>
            ))}
          </div>
        </section>

        {/* Quick Stats - Mobile: 2 columns, Desktop: 4 columns */}
        <section className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
          <HighlightStat label="可信度" value={healthCopy[overallHealth] || '待确认'} tone={overallHealth} />
          <HighlightStat label="覆盖" value={`${health.universe?.active_count || ranking.length} 只`} detail="" />
          <HighlightStat label="信号" value={signals.length ? `${signals.length} 个` : '暂无'} detail="" />
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-3">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">回测</div>
            <div className={`mt-1 text-base font-semibold ${safeNum(backtestSummary.total_return, 0) >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
              {backtestSummary.total_return !== undefined ? pct(backtestSummary.total_return) : '-'}
            </div>
            <div className="mt-0.5 text-[10px] text-zinc-500">回撤 {pct(backtestSummary.max_drawdown || 0)}</div>
          </div>
        </section>

        {/* Section 1: Holdings */}
        <div>
          <SectionHeader
            title="建议持仓"
            subtitle="点击卡片查看因子详情"
            isExpanded={expandedSection !== 'holdings' && expandedSection !== null}
            onClick={() => toggleSection('holdings')}
          />
          {expandedSection !== 'holdings' && (
            <div className="space-y-2 sm:space-y-3">
              {/* Holdings List */}
              <div className="space-y-2">
                {holdings.map((item, idx) => (
                  <HoldingCard
                    key={item.code}
                    item={item}
                    idx={idx}
                    rankingData={ranking}
                    isExpanded={expandedCode === item.code}
                    onToggle={() => toggleCodeExpand(item.code)}
                    activeFactors={activeFactors}
                  />
                ))}
              </div>

              {/* Execution Checklist */}
              <Card title="执行清单">
                <div className="space-y-2">
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-2.5">
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500">规则</div>
                    <div className="mt-1 text-xs text-zinc-200">
                      前 {recommendation.top_n || 0} 名买入，跌出前 {recommendation.buffer_n || 0} 名卖出，{recommendation.rebalance_frequency === 'weekly' ? '周' : '月'}度调仓。
                    </div>
                  </div>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-2.5">
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500">信号</div>
                    <div className="mt-1 space-y-1">
                      {signals.length === 0 ? (
                        <div className="flex items-center gap-1.5 text-zinc-400 text-xs">
                          <span>维持现有持仓</span>
                        </div>
                      ) : (
                        signals.map((signal, index) => (
                          <div key={`${signal.code}-${index}`} className="flex items-center justify-between rounded bg-zinc-950 px-2 py-1">
                            <span className="font-mono text-xs">{signal.code}</span>
                            <span className={`text-xs ${signal.action === 'buy' ? 'text-emerald-300' : 'text-red-300'}`}>
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
            title="数据健康度"
            subtitle="确认数据可信度"
            isExpanded={expandedSection !== 'health' && expandedSection !== null}
            onClick={() => toggleSection('health')}
          />
          {expandedSection !== 'health' && (
            <div className="grid gap-3 sm:gap-4 grid-cols-3">
              {overviewHealth.map(item => (
                <div key={item.label} className={`rounded-xl border p-2.5 ${statusTone[item.value] || 'border-zinc-700 bg-zinc-900 text-zinc-200'}`}>
                  <div className="text-[10px] uppercase tracking-wider opacity-80">{item.label}</div>
                  <div className="mt-1 text-sm font-medium">{item.value}</div>
                  <div className="mt-0.5 text-[10px] opacity-80 truncate">{item.detail}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Section 3: Ranking - Mobile: Full Cards, Desktop: Table */}
        <div>
          <SectionHeader
            title="完整排名"
            subtitle="全部标的比较"
            isExpanded={expandedSection !== 'ranking' && expandedSection !== null}
            onClick={() => toggleSection('ranking')}
          />
          {expandedSection !== 'ranking' && (
            <div>
              {/* Mobile: Full Card List */}
              <div className="lg:hidden grid gap-2">
                {ranking.map(item => (
                  <RankingCard
                    key={item.code}
                    item={item}
                    onSelect={onSelectCode}
                    isActive={selectedCode === item.code}
                  />
                ))}
              </div>

              {/* Desktop: Table View */}
              <div className="hidden lg:block rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
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
                      {ranking.map(item => (
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
            </div>
          )}
        </div>

        {/* Section 4: Backtest */}
        <div>
          <SectionHeader
            title="回测分析"
            subtitle="历史表现参考"
            isExpanded={expandedSection !== 'backtest' && expandedSection !== null}
            onClick={() => toggleSection('backtest')}
          />
          {expandedSection !== 'backtest' && (
            <div>
              {backtestData?.chartData?.length ? (
                <Card>
                  <ResponsiveContainer width="100%" height={chartHeight}>
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
                  暂无回测数据
                </div>
              )}
            </div>
          )}
        </div>

        {/* Scroll to Top Button */}
        {showScrollTop && (
          <button
            onClick={scrollToTop}
            className="fixed bottom-20 right-4 sm:right-6 p-3 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-400 shadow-lg transition-all hover:bg-zinc-700 hover:text-white active:scale-95 z-30"
            aria-label="回到顶部"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
          </button>
        )}
      </main>
    </div>
  )
}

export default Dashboard
