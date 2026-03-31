import React from 'react'

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

export const RankingTable = React.memo(({ data, selectedCode, onSelect }) => {
  const activeFactors = data?.factorModel?.active_factors || ['momentum', 'trend', 'value', 'relative_strength']

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-925 bg-zinc-900/60 p-5">
      <div className="mb-4">
        <h2 className="text-lg font-semibold">指数排名（共 {data?.ranking?.length || 0} 只）</h2>
        <p className="mt-1 text-sm text-zinc-500">保留完整横截面信息，服务复盘与人工判断</p>
      </div>
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
            {data?.ranking?.map(item => (
              <tr
                key={item.code}
                className={`border-b border-zinc-900 hover:bg-zinc-900/80 ${selectedCode === item.code ? 'bg-zinc-900' : ''}`}
                onClick={() => onSelect(item.code)}
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
    </section>
  )
})

RankingTable.displayName = 'RankingTable'
