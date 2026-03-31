import React from 'react'
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Tooltip, BarChart, CartesianGrid, XAxis, YAxis, Bar } from 'recharts'
import { Card, AttributionRow } from '../components/Card'
import { safeNum, factorNames } from '../utils'

const FactorsPage = ({ data, selected, activeFactors, auxFactors }) => {
  const selectedFactors = selected?.factors || {}

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

  return (
    <>
      <section className="grid gap-4 lg:grid-cols-[1.2fr_1fr] animate-fade-in">
        <Card title={`${selected.name} · 因子画像`} subtitle="主模型与辅助因子分开展示，避免解释和主分混淆">
          <div className="grid gap-3 md:grid-cols-3">
            {[...activeFactors, ...auxFactors].map((key, idx) => (
              <div key={key} className="group rounded-xl border border-zinc-800 bg-zinc-900/70 p-4 transition-all duration-300 hover:border-zinc-700 hover:bg-zinc-900 hover:shadow-lg">
                <div className="text-xs uppercase tracking-wider text-zinc-500">{factorNames[key] || key}</div>
                <div className={`mt-2 text-2xl font-semibold ${idx < activeFactors.length ? 'text-gradient-amber' : 'text-gradient'}`}>
                  {safeNum(selectedFactors[key], 0.5).toFixed(2)}
                </div>
                <div className="mt-2 h-2 rounded-full bg-zinc-800">
                  <div
                    className={`h-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-400 transition-all duration-500 ${idx >= activeFactors.length ? 'from-blue-400 to-cyan-400' : ''}`}
                    style={{ width: `${safeNum(selectedFactors[key], 0.5) * 100}%` }}
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

      <section className="grid gap-4 lg:grid-cols-2 animate-slide-up">
        <Card title="主模型雷达图" subtitle="只看当前参与总分的因子">
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#3f3f46" />
              <PolarAngleAxis dataKey="factor" tick={{ fill: '#a1a1aa', fontSize: 12 }} />
              <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fill: '#71717a', fontSize: 10 }} />
              <Radar name="score" dataKey="score" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.2} />
              <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="因子横向对比" subtitle="主模型与辅助因子一起看，但不混入口径">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={factorBarData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 1]} tick={{ fill: '#71717a', fontSize: 10 }} />
              <YAxis dataKey="name" type="category" tick={{ fill: '#a1a1aa', fontSize: 11 }} width={60} />
              <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
              <Bar dataKey="score" fill="#fafafa" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </section>
    </>
  )
}

export default FactorsPage
