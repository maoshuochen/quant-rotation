import React, { useState, useMemo } from 'react'
import { safeNum, factorNames, dedupeHistoryByDate } from '../utils'

const HistoryPanel = ({ historyData, activeFactors, selectedCode, onSelectCode }) => {
  const [selectedPeriod, setSelectedPeriod] = useState(null)
  const [expandedPeriod, setExpandedPeriod] = useState(null)

  const history = historyData?.history || []
  const updateTime = historyData?.updateTime || historyData?.update_time || ''

  // 按日期倒序排列
  const sortedHistory = useMemo(() => {
    return dedupeHistoryByDate(history).sort((a, b) => new Date(b.date) - new Date(a.date))
  }, [history])

  // 获取最新周期
  const latestPeriod = sortedHistory[0]

  const togglePeriodExpand = (date) => {
    setExpandedPeriod(expandedPeriod === date ? null : date)
  }

  if (!history.length) {
    return (
      <div className="mx-auto max-w-7xl px-3 sm:px-4 py-6">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 text-center text-zinc-400">
          <p>暂无历史数据</p>
          <p className="text-xs mt-2 opacity-60">请运行 scripts/generate_data.py 生成前端数据</p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl px-3 sm:px-4 py-6 space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-lg sm:text-xl font-semibold text-zinc-100">历史周期持仓</h1>
          <p className="text-xs sm:text-sm text-zinc-500 mt-1">
            共 {sortedHistory.length} 个周期 · {sortedHistory[0]?.date} ~ {sortedHistory[sortedHistory.length - 1]?.date}
          </p>
        </div>
        {updateTime && (
          <div className="text-xs text-zinc-500 text-right">
            <div>更新于</div>
            <div className="font-mono">{updateTime}</div>
          </div>
        )}
      </header>

      {/* Latest Period Summary */}
      {latestPeriod && (
        <section className="rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-zinc-900/60 p-4 sm:p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            <h2 className="text-sm sm:text-base font-semibold text-amber-500">最新周期</h2>
          </div>
          <div className="text-2xl sm:text-3xl font-bold text-zinc-100">{latestPeriod.date}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {latestPeriod.holdings.map((h, idx) => (
              <button
                key={h.code}
                onClick={() => onSelectCode(h.code)}
                className={`rounded-full px-3 py-1.5 text-xs transition-all ${
                  selectedCode === h.code
                    ? 'bg-amber-500 text-white'
                    : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                }`}
              >
                {h.name} {h.score.toFixed(2)}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* History Timeline */}
      <section>
        <h2 className="text-sm font-semibold text-zinc-400 mb-3">历史周期</h2>
        <div className="space-y-2">
          {sortedHistory.map((period, index) => (
            <div
              key={period.date}
              className={`rounded-xl border transition-all ${
                expandedPeriod === period.date
                  ? 'border-zinc-700 bg-zinc-900'
                  : 'border-zinc-800 bg-zinc-900/50 hover:border-zinc-700'
              }`}
            >
              {/* Period Header */}
              <div
                className="flex items-center justify-between p-3 sm:p-4 cursor-pointer"
                onClick={() => togglePeriodExpand(period.date)}
              >
                <div className="flex items-center gap-3">
                  <span className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${
                    index === 0 ? 'bg-amber-500 text-white' : 'bg-zinc-800 text-zinc-400'
                  }`}>
                    {index + 1}
                  </span>
                  <div>
                    <div className="font-medium text-zinc-100">{period.date}</div>
                    <div className="text-xs text-zinc-500">
                      {period.holdings.length} 只持仓
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {/* Top 3 holdings preview */}
                  <div className="hidden sm:flex items-center gap-2">
                    {period.holdings.slice(0, 3).map((h, i) => (
                      <span
                        key={h.code}
                        className={`text-xs px-2 py-1 rounded-full ${
                          i === 0 ? 'bg-amber-500/20 text-amber-400' :
                          i === 1 ? 'bg-zinc-700 text-zinc-300' :
                          'bg-amber-700/20 text-amber-700'
                        }`}
                      >
                        {h.name}
                      </span>
                    ))}
                  </div>
                  <svg
                    className={`h-5 w-5 text-zinc-500 transition-transform ${
                      expandedPeriod === period.date ? 'rotate-180' : ''
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {/* Expanded Content */}
              {expandedPeriod === period.date && (
                <div className="border-t border-zinc-800 p-4 space-y-4">
                  {/* Holdings Table */}
                  <div>
                    <h3 className="text-xs font-semibold text-zinc-400 mb-2">建议持仓</h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-xs">
                        <thead>
                          <tr className="text-left text-[10px] uppercase tracking-wider text-zinc-500 border-b border-zinc-800">
                            <th className="px-2 py-2">#</th>
                            <th className="px-2 py-2">名称</th>
                            <th className="px-2 py-2">ETF</th>
                            <th className="px-2 py-2">得分</th>
                            {activeFactors.map(key => (
                              <th key={key} className="px-2 py-2 text-right">{factorNames[key]}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {period.holdings.map((item, idx) => (
                            <tr
                              key={item.code}
                              className={`border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer ${
                                selectedCode === item.code ? 'bg-zinc-800/50' : ''
                              }`}
                              onClick={() => onSelectCode(item.code)}
                            >
                              <td className="px-2 py-2 font-mono text-zinc-400">
                                {idx === 0 ? (
                                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-white">
                                    {item.rank}
                                  </span>
                                ) : (
                                  <span className="text-zinc-500">{item.rank}</span>
                                )}
                              </td>
                              <td className="px-2 py-2 font-medium text-zinc-200">{item.name}</td>
                              <td className="px-2 py-2 text-zinc-400 font-mono text-[10px]">{item.etf}</td>
                              <td className="px-2 py-2 font-mono text-amber-400">{item.score.toFixed(3)}</td>
                              {activeFactors.map(key => (
                                <td key={key} className="px-2 py-2 text-right font-mono text-zinc-400 text-[10px]">
                                  {safeNum(item.factors?.[key], 0.5).toFixed(2)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Full Ranking */}
                  {period.ranking && period.ranking.length > 5 && (
                    <div>
                      <h3 className="text-xs font-semibold text-zinc-400 mb-2">完整排名 (Top 20)</h3>
                      <div className="grid gap-1.5">
                        {period.ranking.map((item, idx) => (
                          <div
                            key={item.code}
                            className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs cursor-pointer transition ${
                              selectedCode === item.code
                                ? 'bg-amber-500/10 border border-amber-500/30'
                                : 'bg-zinc-800/50 hover:bg-zinc-800'
                            }`}
                            onClick={() => onSelectCode(item.code)}
                          >
                            <div className="flex items-center gap-2">
                              <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${
                                item.rank <= 3
                                  ? 'bg-amber-500 text-white'
                                  : 'bg-zinc-700 text-zinc-400'
                              }`}>
                                {item.rank}
                              </span>
                              <span className="font-medium text-zinc-200">{item.name}</span>
                              <span className="text-[10px] text-zinc-500 font-mono">{item.etf}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="font-mono text-amber-400">{item.score.toFixed(3)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="pt-2 border-t border-zinc-800">
                    <button
                      onClick={() => {
                        setSelectedPeriod(period)
                        setExpandedPeriod(null)
                      }}
                      className="w-full py-2 rounded-lg bg-zinc-800 text-zinc-300 text-xs hover:bg-zinc-700 transition"
                    >
                      查看此周期详情
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default HistoryPanel
