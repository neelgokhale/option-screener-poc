import type { ReportTradeItem } from '../types'

interface Props {
  trades: ReportTradeItem[]
}

function formatPnl(pnl: number | null): string {
  if (pnl === null) return '—'
  const sign = pnl >= 0 ? '+' : ''
  return `${sign}${pnl.toFixed(2)}%`
}

export default function ResolvedTradesTable({ trades }: Props) {
  if (trades.length === 0) {
    return (
      <div className="text-terminal-muted text-sm py-4 text-center">
        No resolved trades.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-terminal-border text-terminal-muted text-xs text-left">
            <th className="px-3 py-2">Symbol</th>
            <th className="px-3 py-2">Expiry</th>
            <th className="px-3 py-2">Strike</th>
            <th className="px-3 py-2">Settlement</th>
            <th className="px-3 py-2">Outcome</th>
            <th className="px-3 py-2">P&L</th>
            <th className="px-3 py-2">Premium</th>
            <th className="px-3 py-2">Safety</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} className="border-b border-terminal-border/50 hover:bg-terminal-surface/50">
              <td className="px-3 py-2 font-bold text-terminal-cyan">{t.symbol}</td>
              <td className="px-3 py-2">{t.expiry}</td>
              <td className="px-3 py-2">{t.strike}</td>
              <td className="px-3 py-2">{t.settlement_price !== null ? t.settlement_price : '—'}</td>
              <td className={`px-3 py-2 font-bold ${t.outcome === 'OTM' ? 'text-terminal-green' : 'text-terminal-red'}`}>
                {t.outcome}
              </td>
              <td className={`px-3 py-2 ${(t.pnl_pct ?? 0) >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                {formatPnl(t.pnl_pct)}
              </td>
              <td className="px-3 py-2">${t.premium.toFixed(2)}</td>
              <td className="px-3 py-2">{t.safety_score !== null ? t.safety_score.toFixed(0) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
