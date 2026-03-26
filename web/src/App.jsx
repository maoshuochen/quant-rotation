import React, { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'
import ReportsPage from './ReportsPage'

const loadData = async () => {
  try {
    const res = await fetch('/ranking.json')
    const data = await res.json()
    return {
      ranking: data.ranking || [],
      factorWeights: data.factor_weights || {},
      scoreWeights: data.score_weights || {},
      factorModel: data.factor_model || {},
      dynamicWeights: data.dynamic_weights || {},
      marketRegime: data.market_regime || 'sideways',
      marketRegimeDesc: data.market_regime_desc || '',
      strategy: data.strategy || {},
      updateTime: data.update_time || '',
      flowDetails: data.flow_details || {},
      recommendation: data.recommendation || {},
      health: data.health || {},
      universe: data.universe || {}
    }
  } catch (err) {
    console.error('加载 ranking.json 失败:', err)
    return null
  }
}

const loadBacktestData = async () => {
  try {
    const res = await fetch('/backtest.json')
    const data = await res.json()
    return {
      summary: data.summary || {},
      chartData: data.chart_data || []
    }
  } catch (err) {
    console.error('加载 backtest.json 失败:', err)
    return null
  }
}

const factorNames = {
  momentum: '动量',
  trend: '趋势',
  value: '估值',
  relative_strength: '强弱',
  volatility: '波动',
  flow: '资金流',
  fundamental: '基本面',
  sentiment: '情绪'
}

const safeNum = (value, fallback = 0) => {
  if (value === null || value === undefined) return fallback
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

const pct = (value, digits = 1) => `${(safeNum(value) * 100).toFixed(digits)}%`

const healthCopy = {
  ok: '数据完整，可直接执行',
  degraded: '部分数据降级，适合结合人工确认',
  snapshot: '份额数据为快照，可用于辅助判断',
  missing: '关键数据缺失，建议暂停执行'
}

const statusTone = {
  ok: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
  degraded: 'text-amber-200 border-amber-500/30 bg-amber-500/10',
  snapshot: 'text-sky-200 border-sky-500/30 bg-sky-500/10',
  missing: 'text-red-200 border-red-500/30 bg-red-500/10'
}

function App() {
  const [data, setData] = useState(null)
  const [backtestData, setBacktestData] = useState(null)
  const [tab, setTab] = useState('overview')
  const [selectedCode, setSelectedCode] = useState(null)

  useEffect(() => {
    loadData().then(result => {
      setData(result)
      if (result?.recommendation?.selected_codes?.length) {
        setSelectedCode(result.recommendation.selected_codes[0])
      } else if (result?.ranking?.length) {
        setSelectedCode(result.ranking[0].code)
      }
    })
    loadBacktestData().then(setBacktestData)
  }, [])

  const selected = useMemo(() => {
    if (!data?.ranking?.length) return null
    return data.ranking.find(item => item.code === selectedCode) || data.ranking[0]
  }, [data, selectedCode])

  const selectedFactors = selected?.factors || {}
  const activeFactors = data?.factorModel?.active_factors || ['momentum', 'trend', 'value', 'relative_strength']
  const auxFactors = data?.factorModel?.auxiliary_factors || ['volatility', 'flow']

  const radarData = activeFactors.map(key => ({
    factor: factorNames[key] || key,
    score: safeNum(selectedFactors[key], 0.5),
    fullMark: 1
  }))

  const factorBarData = [...activeFactors, ...auxFactors]
    .filter(key => selectedFactors[key] !== undefined)
    .map(key => ({
      name: factorNames[key] || key,
      score: safeNum(selectedFactors[key], 0.5)
    }))

  if (!data) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-7 w-7 animate-spin rounded-full border-2 border-white border-r-transparent" />
          <p className="mt-4 text-sm text-zinc-400">正在加载策略看板...</p>
        </div>
      </div>
    )
  }

  const recommendation = data.recommendation || {}
  const health = data.health || {}
  const universe = data.universe || {}
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

  const holdings = recommendation.holdings || []
  const signals = recommendation.signals || []
  const backtestSummary = backtestData?.summary || {}
  const inactiveUniverse = universe.inactive || []
  const healthStates = [health.price_data?.status, health.northbound?.status, health.etf_shares?.status]
  const overallHealth =
    healthStates.includes('missing') ? 'missing' :
      healthStates.includes('degraded') ? 'degraded' :
        healthStates.includes('snapshot') ? 'snapshot' : 'ok'
  const topNames = holdings.slice(0, 3).map(item => item.name).join('、')
  const executionHeadline = signals.length
    ? `当前建议执行 ${signals.length} 个动作，优先关注 ${topNames || '头部候选'}。`
    : `当前无新增调仓动作，继续跟踪 ${topNames || '头部候选'}。`

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Core Rotation</div>
            <h1 className="mt-1 text-xl font-semibold">指数轮动决策面板</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
              <span>{data.updateTime}</span>
              <span className="text-zinc-700">·</span>
              <span>{data.marketRegimeDesc || data.marketRegime}</span>
              <span className="text-zinc-700">·</span>
              <span>模型: {data.factorModel?.baseline_name || 'core_rotation_v1'}</span>
            </div>
          </div>
          <div className="flex gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-1">
            {[
              ['overview', '总览'],
              ['factors', '因子'],
              ['backtest', '回测'],
              ['reports', '报告']
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`rounded-lg px-3 py-1.5 text-sm transition ${
                  tab === key ? 'bg-white text-zinc-950' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6">
        {tab === 'overview' && (
          <>
            <section className="grid gap-4 lg:grid-cols-[1.35fr_0.95fr]">
              <section className="overflow-hidden rounded-3xl border border-zinc-800 bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.16),_transparent_35%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.14),_transparent_30%),linear-gradient(135deg,_rgba(24,24,27,0.96),_rgba(9,9,11,0.98))] p-6">
                <div className="text-xs uppercase tracking-[0.28em] text-zinc-500">Weekly Decision Brief</div>
                <h2 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight">
                  本周主结论：{topNames || '等待新信号'} 仍是当前最值得优先配置的方向。
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-zinc-300">
                  {executionHeadline} 当前市场处于
                  <span className="mx-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-zinc-100">
                    {data.marketRegimeDesc || data.marketRegime}
                  </span>
                  ，主模型只使用 {activeFactors.length} 个因子参与总分，辅助因子仅用于解释和人工复核。
                </p>
                <div className="mt-6 flex flex-wrap gap-2 text-sm">
                  {holdings.slice(0, 5).map(item => (
                    <button
                      key={item.code}
                      onClick={() => {
                        setSelectedCode(item.code)
                        setTab('factors')
                      }}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-zinc-100 transition hover:bg-white/10"
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

            <section className="grid gap-4 md:grid-cols-4">
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
              <Card title="本周建议持仓" subtitle="优先回答“现在该持有什么、为什么持有”">
                <div className="space-y-3">
                  {holdings.map(item => (
                    <button
                      key={item.code}
                      onClick={() => {
                        setSelectedCode(item.code)
                        setTab('factors')
                      }}
                      className="flex w-full items-start justify-between rounded-xl border border-zinc-800 bg-zinc-900/70 p-4 text-left transition hover:border-zinc-700 hover:bg-zinc-900"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-white">
                            {item.rank}
                          </span>
                          <span className="font-medium">{item.name}</span>
                          <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{item.etf}</span>
                        </div>
                        <div className="mt-2 text-sm text-zinc-300">
                          强项：{item.strongest_factors.map(key => factorNames[key] || key).join('、')}
                        </div>
                        <div className="mt-1 text-xs text-zinc-500">
                          需关注：{item.weakest_factors.map(key => factorNames[key] || key).join('、')}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-zinc-500">综合得分</div>
                        <div className="font-mono text-lg">{safeNum(item.score).toFixed(3)}</div>
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
                        <div className="text-zinc-400">当前没有新增买卖信号，维持现有候选持仓。</div>
                      ) : (
                        signals.map((signal, index) => (
                          <div key={`${signal.code}-${index}`} className="flex items-center justify-between rounded-lg bg-zinc-950 px-3 py-2">
                            <span>{signal.code}</span>
                            <span className={signal.action === 'buy' ? 'text-emerald-300' : 'text-red-300'}>
                              {signal.action === 'buy' ? '买入候选' : '卖出候选'}
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
                    <div key={item.label} className={`rounded-xl border p-4 ${statusTone[item.value] || 'border-zinc-700 bg-zinc-900 text-zinc-200'}`}>
                      <div className="text-xs uppercase tracking-wider opacity-80">{item.label}</div>
                      <div className="mt-2 text-lg font-medium">{item.value}</div>
                      <div className="mt-1 text-xs opacity-80">{item.detail}</div>
                    </div>
                  ))}
                </div>
                {!!health.price_data?.stale_codes?.length && (
                  <div className="mt-4 text-sm text-amber-200">
                    价格数据存在较久未更新标的：{health.price_data.stale_codes.join('、')}
                  </div>
                )}
                {!!health.etf_shares?.missing_codes?.length && (
                  <div className="mt-2 text-sm text-zinc-400">
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

              <Card title="主模型权重" subtitle="冻结基线后，只有 4 个因子参与主分">
                <div className="space-y-3">
                  {activeFactors.map(key => {
                    const scoreWeight = safeNum(data.scoreWeights[key] ?? data.factorWeights[key], 0)
                    return (
                      <div key={key}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span>{factorNames[key] || key}</span>
                          <span className="font-mono text-zinc-300">{(scoreWeight * 100).toFixed(0)}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-zinc-800">
                          <div className="h-2 rounded-full bg-white" style={{ width: `${scoreWeight * 100}%` }} />
                        </div>
                      </div>
                    )
                  })}
                  <div className="pt-2 text-xs leading-6 text-zinc-500">
                    辅助因子：{auxFactors.map(key => factorNames[key] || key).join('、')}。<br />
                    实验因子：{(data.factorModel?.experimental_factors || []).map(key => factorNames[key] || key).join('、') || '无'}。
                  </div>
                </div>
              </Card>
            </section>

            <Card title={`指数排名（共 ${data.ranking.length} 只）`} subtitle="保留完整横截面信息，服务复盘与人工判断">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                    <tr>
                      <th className="px-3 py-3">#</th>
                      <th className="px-3 py-3">名称</th>
                      <th className="px-3 py-3">代码</th>
                      <th className="px-3 py-3">ETF</th>
                      <th className="px-3 py-3">总分</th>
                      {activeFactors.map(key => (
                        <th key={key} className="px-3 py-3">{factorNames[key] || key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.ranking.map(item => (
                      <tr
                        key={item.code}
                        className={`border-b border-zinc-900 hover:bg-zinc-900/80 ${selected?.code === item.code ? 'bg-zinc-900' : ''}`}
                        onClick={() => setSelectedCode(item.code)}
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
            </Card>
          </>
        )}

        {tab === 'factors' && selected && (
          <>
            <section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
              <Card title={`${selected.name} · 因子画像`} subtitle="主模型与辅助因子分开展示，避免解释和主分混淆">
                <div className="grid gap-3 md:grid-cols-3">
                  {[...activeFactors, ...auxFactors].map(key => (
                    <div key={key} className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
                      <div className="text-xs uppercase tracking-wider text-zinc-500">{factorNames[key] || key}</div>
                      <div className="mt-2 text-2xl font-semibold">{safeNum(selected.factors?.[key], 0.5).toFixed(2)}</div>
                      <div className="mt-2 h-2 rounded-full bg-zinc-800">
                        <div
                          className="h-2 rounded-full bg-white"
                          style={{ width: `${safeNum(selected.factors?.[key], 0.5) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card title="关键归因" subtitle="把因子分数翻译成更接近交易语言的解释">
                <div className="space-y-3 text-sm text-zinc-300">
                  <AttributionRow label="6 个月收益" value={`${safeNum(selected.attribution?.momentum_6m_return, 0).toFixed(1)}%`} />
                  <AttributionRow label="相对沪深 300" value={`${safeNum(selected.attribution?.relative_return, 0).toFixed(1)}%`} />
                  <AttributionRow label="价格分位" value={`${safeNum(selected.attribution?.value_percentile, 50).toFixed(0)}%`} />
                  <AttributionRow label="相对 MA20" value={`${safeNum(selected.attribution?.price_vs_ma20, 0).toFixed(1)}%`} />
                  <AttributionRow label="相对 MA60" value={`${safeNum(selected.attribution?.price_vs_ma60, 0).toFixed(1)}%`} />
                  <AttributionRow label="北向资金 20 日" value={`${safeNum(selected.attribution?.northbound_20d_sum, 0).toFixed(1)} 亿`} />
                  <AttributionRow label="ETF 份额 20 日" value={`${safeNum(selected.attribution?.etf_shares_20d_change, 0).toFixed(1)}%`} />
                </div>
              </Card>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <Card title="主模型雷达图" subtitle="只看当前参与总分的 4 个因子">
                <ResponsiveContainer width="100%" height={260}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#3f3f46" />
                    <PolarAngleAxis dataKey="factor" tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fill: '#71717a', fontSize: 10 }} />
                    <Radar name="score" dataKey="score" stroke="#fafafa" fill="#fafafa" fillOpacity={0.15} />
                    <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a' }} />
                  </RadarChart>
                </ResponsiveContainer>
              </Card>

              <Card title="因子横向对比" subtitle="主模型与辅助因子一起看，但不混入口径">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={factorBarData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                    <XAxis type="number" domain={[0, 1]} tick={{ fill: '#71717a', fontSize: 10 }} />
                    <YAxis dataKey="name" type="category" tick={{ fill: '#a1a1aa', fontSize: 11 }} width={60} />
                    <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a' }} />
                    <Bar dataKey="score" fill="#fafafa" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </section>
          </>
        )}

        {tab === 'backtest' && (
          <div className="space-y-4">
            <section className="grid gap-4 md:grid-cols-4">
              <MetricCard label="总收益" value={backtestSummary.total_return !== undefined ? pct(backtestSummary.total_return) : '暂无'} positive={safeNum(backtestSummary.total_return, 0) >= 0} />
              <MetricCard label="年化收益" value={backtestSummary.annual_return !== undefined ? pct(backtestSummary.annual_return) : '暂无'} positive={safeNum(backtestSummary.annual_return, 0) >= 0} />
              <MetricCard label="最大回撤" value={backtestSummary.max_drawdown !== undefined ? pct(backtestSummary.max_drawdown) : '暂无'} positive={false} />
              <MetricCard label="夏普比率" value={backtestSummary.sharpe_ratio !== undefined ? String(backtestSummary.sharpe_ratio) : '暂无'} sub={backtestSummary.period ? `${backtestSummary.period.start} → ${backtestSummary.period.end}` : ''} />
            </section>

            <Card title="净值与回撤" subtitle="先看收益，再看回撤，再决定要不要继续信任策略">
              {backtestData?.chartData?.length ? (
                <ResponsiveContainer width="100%" height={320}>
                  <AreaChart data={backtestData.chartData}>
                    <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} minTickGap={32} />
                    <YAxis tick={{ fill: '#71717a', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a' }} />
                    <Area type="monotone" dataKey="cum_return" stroke="#fafafa" fill="#fafafa" fillOpacity={0.16} />
                    <Area type="monotone" dataKey="drawdown" stroke="#f87171" fill="#f87171" fillOpacity={0.1} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-6 text-sm text-zinc-400">
                  尚未生成可用的回测图表数据。
                </div>
              )}
            </Card>
          </div>
        )}

        {tab === 'reports' && <ReportsPage />}
      </main>
    </div>
  )
}

const Card = ({ title, subtitle, children }) => (
  <section className="rounded-2xl border border-zinc-800 bg-zinc-925 bg-zinc-900/60 p-5">
    <div className="mb-4">
      <h2 className="text-lg font-semibold">{title}</h2>
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
  <div className={`rounded-2xl border p-4 ${statusTone[tone] || 'border-zinc-800 bg-zinc-900/60 text-zinc-50'}`}>
    <div className="text-xs uppercase tracking-wider opacity-80">{label}</div>
    <div className="mt-2 text-lg font-semibold">{value}</div>
    {detail ? <div className="mt-1 text-xs opacity-80">{detail}</div> : null}
  </div>
)

const AttributionRow = ({ label, value }) => (
  <div className="flex items-center justify-between rounded-lg bg-zinc-900/70 px-3 py-2">
    <span className="text-zinc-500">{label}</span>
    <span className="font-mono text-zinc-100">{value}</span>
  </div>
)

export default App
