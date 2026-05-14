import type { ReportTradeItem } from '../types'

interface Props {
  trades: ReportTradeItem[]
  onRefresh?: () => void
}

export default function ActiveTradesTable({ trades, onRefresh }: Props) {
  if (trades.length === 0) {
    return (
      <div className="text-terminal-muted text-sm py-4 text-center">
        No active trades.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      {onRefresh && (
        <div className="mb-2">
          <button
            onClick={onRefresh}
            className="px-3 py-1 bg-terminal-cyan/20 text-terminal-cyan border border-terminal-cyan/30 rounded text-sm hover:bg-terminal-cyan/30 transition-colors"
          >
            Refresh Prices
          </button>
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-terminal-border text-terminal-muted text-xs text-left">
            <th className="px-3 py-2">Symbol</th>
            <th className="px-3 py-2">Expiry</th>
            <th className="px-3 py-2">Strike</th>
            <th className="px-3 py-2">Price</th>
            <th className="px-3 py-2">Premium</th>
            <th className="px-3 py-2">POP</th>
            <th className="px-3 py-2">DTE</th>
            <th className="px-3 py-2">Safety</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} className="border-b border-terminal-border/50 hover:bg-terminal-surface/50">
              <td className="px-3 py-2 font-bold text-terminal-cyan">{t.symbol}</td>
              <td className="px-3 py-2">{t.expiry}</td>
              <td className="px-3 py-2">{t.strike}</td>
              <td className="px-3 py-2">{t.current_price}</td>
              <td className="px-3 py-2">${t.premium.toFixed(2)}</td>
              <td className="px-3 py-2">{(t.pop * 100).toFixed(0)}%</td>
              <td className="px-3 py-2">{t.days_remaining !== null ? `${t.days_remaining}d` : '—'}</td>
              <td className="px-3 py-2">{t.safety_score !== null ? t.safety_score.toFixed(0) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
