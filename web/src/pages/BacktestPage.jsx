import React from 'react'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import { Card, MetricCard } from '../components/Card'
import { safeNum, pct } from '../utils'

const BacktestPage = ({ backtestData }) => {
  const backtestSummary = backtestData?.summary || {}

  return (
    <div className="space-y-4">
      <section className="grid gap-4 md:grid-cols-4">
        <MetricCard
          label="总收益"
          value={backtestSummary.total_return !== undefined ? pct(backtestSummary.total_return) : '暂无'}
          positive={safeNum(backtestSummary.total_return, 0) >= 0}
        />
        <MetricCard
          label="年化收益"
          value={backtestSummary.annual_return !== undefined ? pct(backtestSummary.annual_return) : '暂无'}
          positive={safeNum(backtestSummary.annual_return, 0) >= 0}
        />
        <MetricCard
          label="最大回撤"
          value={backtestSummary.max_drawdown !== undefined ? pct(backtestSummary.max_drawdown) : '暂无'}
          positive={false}
        />
        <MetricCard
          label="夏普比率"
          value={backtestSummary.sharpe_ratio !== undefined ? String(backtestSummary.sharpe_ratio) : '暂无'}
          sub={backtestSummary.period ? `${backtestSummary.period.start} → ${backtestSummary.period.end}` : ''}
        />
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
  )
}

export default BacktestPage
