import React, { useState, useEffect } from 'react'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import { safeNum, pct, factorNames } from '../utils'

const Card = ({ title, subtitle, children, className = '' }) => (
  <section className={`rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 sm:p-5 ${className}`}>
    <div className="mb-4">
      <h2 className="text-base sm:text-lg font-semibold text-zinc-100">{title}</h2>
      {subtitle ? <p className="mt-1 text-xs sm:text-sm text-zinc-500">{subtitle}</p> : null}
    </div>
    {children}
  </section>
)

const HighlightStat = ({ label, value, detail }) => (
  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-3 sm:p-4 text-zinc-50">
    <div className="text-[10px] sm:text-xs uppercase tracking-wider opacity-80">{label}</div>
    <div className="mt-1.5 sm:mt-2 text-base sm:text-lg font-semibold">{value}</div>
    {detail ? <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-xs opacity-80">{detail}</div> : null}
  </div>
)

const SectionHeader = ({ title, subtitle, isExpanded, onClick, actions }) => (
  <button
    onClick={onClick}
    className="w-full text-left mb-3 sm:mb-4 group"
    aria-expanded={isExpanded}
  >
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0 flex items-center gap-2 sm:gap-3">
        <span className={`h-2 w-2 rounded-full transition-colors ${isExpanded ? 'bg-amber-500' : 'bg-zinc-600'}`} />
        <div className="min-w-0">
          <h2 className="text-base sm:text-xl font-semibold text-zinc-100">{title}</h2>
          {subtitle && <p className="mt-1 text-xs sm:text-sm text-zinc-500">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {actions ? <div onClick={(e) => e.stopPropagation()}>{actions}</div> : null}
        <svg
          className={`h-5 w-5 text-zinc-500 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>
  </button>
)

// 统一的排名列表项组件
const RankingListItem = ({ item, isExpanded, onToggle, activeFactors }) => {
  const score = safeNum(item.score).toFixed(3)
  const factors = item.factors || {}
  const attribution = item.attribution || {}
  const isTop3 = item.rank <= 3
  const isTop5 = item.rank <= 5

  // 排名徽章样式
  const getRankBadge = () => {
    if (item.rank === 1) return 'bg-amber-500 text-white'
    if (item.rank === 2) return 'bg-zinc-400 text-white'
    if (item.rank === 3) return 'bg-amber-700 text-white'
    if (isTop5) return 'bg-white/10 text-zinc-200'
    return 'bg-zinc-800 text-zinc-400'
  }

  // 卡片背景样式
  const getBgStyle = () => {
    if (isTop3) return 'border-amber-500/30 bg-amber-500/5'
    if (isTop5) return 'border-amber-500/20 bg-zinc-900/70'
    return 'border-zinc-800 bg-zinc-900/70'
  }

  return (
    <div className={`rounded-xl border transition-all duration-300 ${getBgStyle()}`}>
      <div
        className="flex items-center justify-between p-3 sm:p-4 cursor-pointer active:bg-zinc-800/50"
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onToggle()}
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
          {/* 排名徽章 */}
          <span className={`flex-shrink-0 inline-flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-full text-xs sm:text-sm font-semibold ${getRankBadge()}`}>
            {item.rank === 1 ? '🏆' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : item.rank}
          </span>

          {/* 名称和代码 */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className={`font-medium truncate ${isTop5 ? 'text-zinc-100' : 'text-zinc-300'}`}>
                {item.name}
              </span>
              {isTop5 && (
                <span className="flex-shrink-0 rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px] sm:text-xs text-amber-300 font-medium">
                  推荐
                </span>
              )}
              <span className="flex-shrink-0 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] sm:text-xs text-zinc-400 font-mono">
                {item.etf}
              </span>
            </div>
            {/* 强项因子 */}
            <div className="text-[10px] sm:text-xs text-zinc-500 mt-0.5 truncate">
              {(() => {
                const sortedFactors = Object.entries(factors)
                  .sort(([,a], [,b]) => b - a)
                  .slice(0, 2)
                  .map(([key]) => factorNames[key] || key)
                return `强项：${sortedFactors.join('、') || '-'}`
              })()}
            </div>
          </div>
        </div>

        {/* 得分 */}
        <div className="flex-shrink-0 text-right ml-2">
          <div className="text-[10px] sm:text-xs text-zinc-500">得分</div>
          <div className="font-mono text-sm sm:text-lg text-gradient">{score}</div>
        </div>
      </div>

      {/* 展开详情 */}
      {isExpanded && (
        <div className="border-t border-zinc-800 p-3 sm:p-4 bg-zinc-950/50 space-y-3">
          {/* 因子得分 */}
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

          {/* 关键归因 */}
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

const Dashboard = ({
  data,
  backtestData,
  historyData,
  selected,
  selectedCode,
  activeFactors,
  expandedSection,
  setExpandedSection,
  onSelectCode,
  refreshing,
  onRefresh,
  theme,
  onToggleTheme
}) => {
  const [expandedCode, setExpandedCode] = useState(null)
  const [showScrollTop, setShowScrollTop] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState('current')

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
  const universe = data?.universe || {}
  const holdings = recommendation.holdings || []
  const signals = recommendation.signals || []
  const backtestSummary = backtestData?.summary || {}
  const inactiveUniverse = universe.inactive || []
  const ranking = data?.ranking || []
  const history = historyData?.history || []
  const sortedHistory = [...history].sort((a, b) => new Date(b.date) - new Date(a.date))
  const latestHistoryDate = sortedHistory[0]?.date || ''
  const historicalOptions = latestHistoryDate
    ? sortedHistory.filter((period) => period.date !== latestHistoryDate)
    : sortedHistory
  const selectedHistoryPeriod = selectedPeriod === 'current'
    ? null
    : sortedHistory.find((period) => period.date === selectedPeriod) || null
  const rankingView = selectedHistoryPeriod?.holdings || ranking

  const topNames = holdings.slice(0, 3).map(item => item.name).join(', ')
  const executionHeadline = signals.length
    ? `建议执行 ${signals.length} 个动作，关注 ${topNames || '头部'}。`
    : `无新增动作，跟踪 ${topNames || '头部候选'}。`

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  const toggleCodeExpand = (code) => {
    setExpandedCode(expandedCode === code ? null : code)
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      {/* Mobile-optimized Header */}
      <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-3 sm:px-4 py-3 sm:py-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Core</span>
              <h1 className="text-sm sm:text-lg font-semibold text-gradient truncate">指数轮动</h1>
              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] sm:text-xs text-zinc-300">
                {data.marketRegimeDesc || data.marketRegime}
              </span>
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
          <button
            onClick={onToggleTheme}
            className="flex-shrink-0 ml-2 p-2 rounded-lg border border-zinc-700 transition-all active:scale-95"
            title={theme === 'dark' ? '切换到浅色模式' : '切换到暗色模式'}
            aria-label={theme === 'dark' ? '切换到浅色模式' : '切换到暗色模式'}
          >
            {theme === 'dark' ? (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v2.25m0 13.5V21m9-9h-2.25M5.25 12H3m15.114 6.364-1.591-1.591M7.477 7.477 5.886 5.886m12.228 0-1.591 1.591M7.477 16.523l-1.591 1.591M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            ) : (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12.79A9 9 0 1111.21 3c0 .34.02.67.05 1A7 7 0 0020 12c.33.03.66.05 1 .05z" />
              </svg>
            )}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-3 sm:px-4 py-4 sm:py-6 space-y-4 sm:space-y-6 pb-20">
        {/* Section 1: Unified Ranking List (merged holdings + signals) */}
        <div>
          <SectionHeader
            title="全部排名"
            subtitle={selectedHistoryPeriod ? `查看 ${selectedHistoryPeriod.date} 周期持仓快照` : '调仓规则、当前信号与完整排名'}
            isExpanded={expandedSection !== 'ranking' && expandedSection !== null}
            onClick={() => toggleSection('ranking')}
            actions={
              <label className="flex items-center gap-2 text-xs text-zinc-400">
                <span className="hidden sm:inline">周期</span>
                <select
                  value={selectedPeriod}
                  onChange={(e) => {
                    const nextPeriod = e.target.value
                    setSelectedPeriod(nextPeriod)
                    setExpandedCode(null)
                  }}
                  className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 outline-none focus:border-amber-500"
                  aria-label="选择周期"
                >
                  <option value="current">{latestHistoryDate ? `${latestHistoryDate}（最新周期）` : '最新周期'}</option>
                  {historicalOptions.map((period) => (
                    <option key={period.date} value={period.date}>
                      {period.date}
                    </option>
                  ))}
                </select>
              </label>
            }
          />
          {expandedSection !== 'ranking' && (
            <div>
              <div className="mb-3 space-y-2">
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">调仓规则</div>
                  <div className="mt-1 text-xs text-zinc-200">
                    前 {recommendation.top_n || 0} 名买入，跌出前 {recommendation.buffer_n || 0} 名卖出，
                    {recommendation.rebalance_frequency === 'weekly' ? '每周' : '每月'}调仓。
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">
                    {selectedHistoryPeriod ? '历史说明' : '本期信号'}
                  </div>
                  <div className="mt-1 text-xs text-zinc-200">
                    {selectedHistoryPeriod ? (
                      <span>{selectedHistoryPeriod.date} 为历史周期快照，仅展示当期建议持仓，不回放当周交易信号。</span>
                    ) : signals.length === 0 ? (
                      <span>当前无新增调仓动作，维持现有持仓。</span>
                    ) : (
                      <span>
                        {signals.map(signal => `${signal.action === 'buy' ? '买入' : '卖出'} ${signal.name || signal.code}`).join('；')}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Mobile: Unified Card List */}
              <div className="lg:hidden grid gap-2">
                {rankingView.map(item => (
                  <RankingListItem
                    key={item.code}
                    item={item}
                    isExpanded={expandedCode === item.code}
                    onToggle={() => toggleCodeExpand(item.code)}
                    activeFactors={activeFactors}
                  />
                ))}
              </div>

              {/* Desktop: Table View with visual distinction */}
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
                      {rankingView.map(item => {
                        const isTop5 = selectedPeriod === 'current' && item.rank <= 5
                        return (
                          <tr
                            key={item.code}
                            className={`border-b border-zinc-900 hover:bg-zinc-900/80 ${
                              selectedCode === item.code ? 'bg-zinc-900' : ''
                            } ${isTop5 ? 'bg-amber-500/5' : ''}`}
                            onClick={() => onSelectCode(item.code)}
                          >
                            <td className="px-3 py-3 font-mono text-zinc-400">
                              {item.rank === 1 ? '🏆' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : item.rank}
                            </td>
                            <td className={`px-3 py-3 ${isTop5 ? 'text-amber-100 font-medium' : 'text-zinc-200'}`}>
                              {item.name}
                              {isTop5 && <span className="ml-2 text-[9px] text-amber-400">推荐</span>}
                            </td>
                            <td className="px-3 py-3 font-mono text-xs text-zinc-400">{item.code}</td>
                            <td className="px-3 py-3 text-zinc-400">{item.etf}</td>
                            <td className={`px-3 py-3 font-mono ${isTop5 ? 'text-amber-300' : 'text-zinc-200'}`}>{safeNum(item.score).toFixed(3)}</td>
                            {activeFactors.map(key => (
                              <td key={key} className="px-3 py-3 font-mono text-zinc-300">
                                {safeNum(item.factors?.[key], 0.5).toFixed(2)}
                              </td>
                            ))}
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Section 2: Backtest */}
        <div>
          <SectionHeader
            title="回测分析"
            subtitle="回测摘要与历史表现"
            isExpanded={expandedSection !== 'backtest' && expandedSection !== null}
            onClick={() => toggleSection('backtest')}
          />
          {expandedSection !== 'backtest' && (
            <div>
              {backtestData?.chartData?.length ? (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 sm:p-5">
                  <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <HighlightStat
                      label="总收益"
                      value={backtestSummary.total_return !== undefined ? pct(backtestSummary.total_return) : '-'}
                      detail={backtestSummary.period ? `${backtestSummary.period.start} ~ ${backtestSummary.period.end}` : ''}
                    />
                    <HighlightStat
                      label="最大回撤"
                      value={backtestSummary.max_drawdown !== undefined ? pct(backtestSummary.max_drawdown) : '-'}
                      detail={backtestSummary.max_drawdown_date || ''}
                    />
                    <HighlightStat
                      label="夏普"
                      value={safeNum(backtestSummary.sharpe_ratio, 0).toFixed(2)}
                      detail={`${safeNum(backtestSummary.trading_days, 0)} 个交易日`}
                    />
                    <HighlightStat
                      label="期末净值"
                      value={backtestSummary.final_value ? safeNum(backtestSummary.final_value, 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '-'}
                      detail="初始资金 1,000,000"
                    />
                  </div>
                  <div className="h-[220px] sm:h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
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
                        <CartesianGrid stroke={theme === 'dark' ? '#27272a' : '#d6d3d1'} strokeDasharray="3 3" />
                        <XAxis dataKey="date" tick={{ fill: theme === 'dark' ? '#71717a' : '#6b7280', fontSize: 10 }} minTickGap={32} />
                        <YAxis tick={{ fill: theme === 'dark' ? '#71717a' : '#6b7280', fontSize: 10 }} />
                        <Tooltip contentStyle={{ background: theme === 'dark' ? '#18181b' : '#fffaf2', border: `1px solid ${theme === 'dark' ? '#27272a' : '#d6d3d1'}`, borderRadius: '8px', color: theme === 'dark' ? '#f4f4f5' : '#1f2937' }} />
                        <Area type="monotone" dataKey="cum_return" stroke="#f59e0b" fill="url(#colorReturn)" strokeWidth={2} />
                        <Area type="monotone" dataKey="drawdown" stroke="#f87171" fill="url(#colorDrawdown)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
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
