import { useState } from 'react'
import type { TradeOutput } from '../types'
import type { Filters } from './FilterPanel'
import Tooltip from './Tooltip'
import TradeRow from './TradeRow'
import TradeDetail from './TradeDetail'

interface Props {
  trades: TradeOutput[]
  filters: Filters
}

const COLUMN_TIPS: Record<string, string> = {
  POP: 'Probability of profit — chance option expires worthless',
  Delta: 'Likelihood of assignment (lower = safer)',
  Theta: 'Daily premium decay in your favor',
  IV: 'Implied volatility — higher means richer premiums but more risk',
  EV: 'Expected value per contract',
  Safety: 'Risk-adjusted safety score (0-1)',
  'Adj Score': 'EV x (1 + Safety) — final ranking metric',
}

export default function TradeTable({ trades, filters }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const filtered = trades.filter((t) => {
    if (t.pop < filters.minPop) return false
    if (t.safety_score !== null && t.safety_score < filters.minSafety) return false
    if (t.days_to_expiry < filters.minExpiry || t.days_to_expiry > filters.maxExpiry) return false
    if (t.premium_yield < filters.minYield) return false
    return true
  })

  const makeId = (t: TradeOutput) => `${t.symbol}-${t.strike}-${t.expiry}`

  if (filtered.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-terminal-muted text-sm py-16">
        {trades.length === 0
          ? 'Run the scanner to find trades'
          : 'No trades match current filters'}
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-terminal-border text-xs text-terminal-muted uppercase tracking-wider">
            <th className="px-2 py-2">#</th>
            <th className="px-2 py-2">Stock</th>
            <th className="px-2 py-2">Strike</th>
            <th className="px-2 py-2">Expiry</th>
            <th className="px-2 py-2">Premium</th>
            <th className="px-2 py-2"><Tooltip text={COLUMN_TIPS.POP}>POP</Tooltip></th>
            <th className="px-2 py-2 hidden md:table-cell"><Tooltip text={COLUMN_TIPS.Delta}>Delta</Tooltip></th>
            <th className="px-2 py-2 hidden md:table-cell"><Tooltip text={COLUMN_TIPS.Theta}>Theta</Tooltip></th>
            <th className="px-2 py-2 hidden md:table-cell"><Tooltip text={COLUMN_TIPS.IV}>IV</Tooltip></th>
            <th className="px-2 py-2 hidden md:table-cell"><Tooltip text={COLUMN_TIPS.EV}>EV</Tooltip></th>
            <th className="px-2 py-2"><Tooltip text={COLUMN_TIPS.Safety}>Safety</Tooltip></th>
            <th className="px-2 py-2 hidden md:table-cell"><Tooltip text={COLUMN_TIPS['Adj Score']}>Adj Score</Tooltip></th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((trade) => {
            const id = makeId(trade)
            const expanded = expandedId === id
            return (
              <TradeRow
                key={id}
                trade={trade}
                expanded={expanded}
                onToggle={() => setExpandedId(expanded ? null : id)}
              />
            )
          })}
        </tbody>
      </table>

      {/* Expanded detail rendered outside table for layout */}
      {expandedId && (() => {
        const trade = filtered.find((t) => makeId(t) === expandedId)
        return trade ? <TradeDetail trade={trade} /> : null
      })()}
    </div>
  )
}
