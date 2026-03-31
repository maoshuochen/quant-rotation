import React from 'react'

export const Card = React.memo(({ title, subtitle, children }) => (
  <section className="rounded-2xl border border-zinc-800 bg-zinc-925 bg-zinc-900/60 p-5">
    <div className="mb-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {subtitle ? <p className="mt-1 text-sm text-zinc-500">{subtitle}</p> : null}
    </div>
    {children}
  </section>
))

Card.displayName = 'Card'

export const MetricCard = React.memo(({ label, value, sub, positive }) => (
  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
    <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
    <div className={`mt-2 text-xl font-semibold ${
      positive === true ? 'text-emerald-300' : positive === false ? 'text-red-300' : 'text-zinc-50'
    }`}>
      {value}
    </div>
    {sub ? <div className="mt-1 text-xs text-zinc-500">{sub}</div> : null}
  </div>
))

MetricCard.displayName = 'MetricCard'

export const HighlightStat = React.memo(({ label, value, detail, tone }) => (
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
))

HighlightStat.displayName = 'HighlightStat'

export const AttributionRow = React.memo(({ label, value }) => (
  <div className="flex items-center justify-between rounded-lg bg-zinc-900/70 px-3 py-2">
    <span className="text-zinc-500">{label}</span>
    <span className="font-mono text-zinc-100">{value}</span>
  </div>
))

AttributionRow.displayName = 'AttributionRow'
