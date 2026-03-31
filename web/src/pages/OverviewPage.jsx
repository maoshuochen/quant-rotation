import React from 'react'
import { Card, MetricCard, HighlightStat } from '../components/Card'
import { RankingTable } from '../components/RankingTable'
import { safeNum, pct, healthCopy, statusTone, factorNames } from '../utils'

const OverviewPage = ({ data, backtestData, selectedCode, onSelectCode }) => {
  const recommendation = data?.recommendation || {}
  const health = data?.health || {}
  const universe = data?.universe || {}
  const holdings = recommendation.holdings || []
  const signals = recommendation.signals || []
  const backtestSummary = backtestData?.summary || {}
  const inactiveUniverse = universe.inactive || []
  const activeFactors = data?.factorModel?.active_factors || []

  const healthStates = [health.price_data?.status, health.northbound?.status, health.etf_shares?.status]
  const overallHealth =
    healthStates.includes('missing') ? 'missing' :
    healthStates.includes('degraded') ? 'degraded' :
    healthStates.includes('snapshot') ? 'snapshot' : 'ok'

  const topNames = holdings.slice(0, 3).map(item => item.name).join('、')
  const executionHeadline = signals.length
    ? `当前建议执行 ${signals.length} 个动作，优先关注 ${topNames || '头部候选'}。`
    : `当前无新增调仓动作，继续跟踪 ${topNames || '头部候选'}。`

  const overviewHealth = [
    { label: '价格数据', value: health.price_data?.status || 'unknown', detail: `${health.price_data?.available_count || 0}/${health.price_data?.expected_count || 0}` },
    {
      label: '北向资金',
      value: health.northbound?.status || 'unknown',
      detail: health.northbound?.latest_valid_date
        ? `历史 ${health.northbound.rows || 0} 日，最近连续 ${health.northbound.recent_rows || 0} 日`
        : `${health.northbound?.rows || 0} rows`
    },
    { label: 'ETF 份额', value: health.etf_shares?.status || 'unknown', detail: `历史 ${health.etf_shares?.history_count || 0} / 快照 ${health.etf_shares?.snapshot_count || 0}` }
  ]

  return (
    <>
      <section className="grid gap-4 lg:grid-cols-[1.35fr_0.95fr]">
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
            ，主模型只使用 {activeFactors.length} 个因子参与总分，辅助因子仅用于解释和人工复核。
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

        <section className="grid gap-4">
          <Card title="执行状态" subtitle="更像 PM 看板的摘要视图">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <HighlightStat label="策略可信度" value={healthCopy[overallHealth] || '待确认'} tone={overallHealth} />
              <HighlightStat
                label="正式覆盖范围"
                value={`${health.universe?.active_count || data.ranking.length} 只活跃指数`}
                detail={inactiveUniverse.length ? `另有 ${inactiveUniverse.length} 只已下线代理` : '当前无下线代理'}
              />
              <HighlightStat
                label="建议动作"
                value={signals.length ? `${signals.length} 个待执行信号` : '以持有观察为主'}
                detail={`最近更新 ${data.updateTime || '--'}`}
              />
            </div>
          </Card>
        </section>
      </section>

      <section className="grid gap-4 md:grid-cols-4 animate-slide-up">
        <MetricCard label="当前市场状态" value={data.marketRegimeDesc || data.marketRegime} sub="基于沪深 300 趋势识别" />
        <MetricCard label="本周建议持仓" value={`${recommendation.top_n || 0} 只`} sub={`缓冲卖出阈值 Top ${recommendation.buffer_n || 0}`} />
        <MetricCard
          label="活跃观察池"
          value={`${health.universe?.active_count || data.ranking.length} 只`}
          sub={inactiveUniverse.length ? `${inactiveUniverse.length} 只代理已下线` : '正式池运行中'}
        />
        <MetricCard
          label="回测快照"
          value={backtestSummary.total_return !== undefined ? pct(backtestSummary.total_return) : '暂无'}
          sub={backtestSummary.max_drawdown !== undefined ? `最大回撤 ${pct(backtestSummary.max_drawdown)}` : '等待回测产物'}
          positive={safeNum(backtestSummary.total_return, 0) >= 0}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Card title="本周建议持仓" subtitle="优先回答&#39;现在该持有什么、为什么持有&#39;">
          <div className="space-y-3">
            {holdings.map((item, idx) => (
              <button
                key={item.code}
                onClick={() => onSelectCode(item.code)}
                className={`flex w-full items-start justify-between rounded-xl border border-zinc-800 bg-zinc-900/70 p-4 text-left transition-all duration-300 hover:border-zinc-700 hover:bg-zinc-900 hover:shadow-lg active:scale-[0.99] ${idx === 0 ? 'glow-amber/20' : ''}`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold text-white ${idx === 0 ? 'bg-amber-500' : idx === 1 ? 'bg-zinc-400' : idx === 2 ? 'bg-amber-700' : 'bg-white/10'}`}>
                      {item.rank}
                    </span>
                    <span className="font-medium text-zinc-100">{item.name}</span>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{item.etf}</span>
                  </div>
                  <div className="mt-2 text-sm text-zinc-300">
                    强项：<span className="text-gradient-amber">{item.strongest_factors?.map(key => factorNames[key] || key).join('、') || '无'}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    需关注：<span className="text-zinc-400">{item.weakest_factors?.map(key => factorNames[key] || key).join('、') || '无'}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-zinc-500">综合得分</div>
                  <div className="font-mono text-lg text-gradient">{safeNum(item.score).toFixed(3)}</div>
                </div>
              </button>
            ))}
          </div>
        </Card>

        <Card title="执行清单" subtitle="把策略输出转成可执行动作">
          <div className="space-y-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
              <div className="text-xs uppercase tracking-wider text-zinc-500">调仓规则</div>
              <div className="mt-2 text-sm text-zinc-200">
                前 {recommendation.top_n || 0} 名买入，跌出前 {recommendation.buffer_n || 0} 名卖出，按{recommendation.rebalance_frequency === 'weekly' ? '周度' : '月度'}调仓。
              </div>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
              <div className="text-xs uppercase tracking-wider text-zinc-500">本次信号</div>
              <div className="mt-2 space-y-2 text-sm">
                {signals.length === 0 ? (
                  <div className="flex items-center gap-2 text-zinc-400">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    当前没有新增买卖信号，维持现有候选持仓。
                  </div>
                ) : (
                  signals.map((signal, index) => (
                    <div key={`${signal.code}-${index}`} className="flex items-center justify-between rounded-lg bg-zinc-950 px-3 py-2">
                      <span className="font-mono text-sm">{signal.code}</span>
                      <span className={`flex items-center gap-1 text-sm ${signal.action === 'buy' ? 'text-emerald-300' : 'text-red-300'}`}>
                        {signal.action === 'buy' ? (
                          <>
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                            买入候选
                          </>
                        ) : (
                          <>
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
                            </svg>
                            卖出候选
                          </>
                        )}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card title="数据与运行健康度" subtitle="先看结果，再确认结果是否值得信任">
          <div className="grid gap-3 md:grid-cols-3">
            {overviewHealth.map(item => (
              <div key={item.label} className={`rounded-xl border p-4 transition-all duration-300 hover:shadow-lg ${statusTone[item.value] || 'border-zinc-700 bg-zinc-900 text-zinc-200'}`}>
                <div className="text-xs uppercase tracking-wider opacity-80">{item.label}</div>
                <div className="mt-2 text-lg font-medium">{item.value}</div>
                <div className="mt-1 text-xs opacity-80">{item.detail}</div>
              </div>
            ))}
          </div>
          {!!health.price_data?.stale_codes?.length && (
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-200">
              <svg className="mt-0.5 h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              价格数据存在较久未更新标的：{health.price_data.stale_codes.join('、')}
            </div>
          )}
          {!!health.etf_shares?.missing_codes?.length && (
            <div className="mt-2 flex items-start gap-2 rounded-xl border border-zinc-700 bg-zinc-800/50 p-3 text-sm text-zinc-400">
              <svg className="mt-0.5 h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              ETF 份额缺失标的：{health.etf_shares.missing_codes.join('、')}
            </div>
          )}
          {!!health.northbound?.latest_valid_date && (
            <div className="mt-2 text-sm text-zinc-400">
              北向资金历史最近有效日期：{health.northbound.latest_valid_date}
              {health.northbound.snapshot_date ? `，当前快照日期：${health.northbound.snapshot_date}` : ''}
              {health.northbound.recent_rows !== undefined ? `，最近连续窗口 ${health.northbound.recent_rows} 日` : ''}
            </div>
          )}
          {!!inactiveUniverse.length && (
            <div className="mt-2 text-sm text-zinc-400">
              已下线代理：{inactiveUniverse.map(item => `${item.name}(${item.etf})`).join('、')}
            </div>
          )}
        </Card>

        <Card title="优化后的因子权重" subtitle="基于多目标贝叶斯优化 (2025-01 ~ 2026-03)">
          <div className="space-y-3">
            {Object.entries(data.factorWeights || {})
              .filter(([_, v]) => safeNum(v) > 0)
              .map(([key, weight]) => (
                <div key={key}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-zinc-300">{factorNames[key] || key}</span>
                    <span className="font-mono text-zinc-300">{(safeNum(weight) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-zinc-800">
                    <div className="h-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-400" style={{ width: `${safeNum(weight) * 100}%` }} />
                  </div>
                </div>
              ))}
            <div className="pt-2 text-xs leading-6 text-zinc-500">
              主模型因子：<span className="text-gradient">{activeFactors.map(key => factorNames[key] || key).join('、')}</span>。
            </div>
          </div>
        </Card>
      </section>

      <RankingTable data={data} selectedCode={selectedCode} onSelect={onSelectCode} />
    </>
  )
}

export default OverviewPage
