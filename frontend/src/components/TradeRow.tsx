import type { TradeOutput } from '../types'
import POPBar from './POPBar'
import SafetyBar from './SafetyBar'

interface Props {
  trade: TradeOutput
  expanded: boolean
  onToggle: () => void
}

export default function TradeRow({ trade, expanded, onToggle }: Props) {
  return (
    <tr
      onClick={onToggle}
      className={`cursor-pointer border-b border-terminal-border/50 hover:bg-terminal-surface/50 transition-colors text-sm ${
        expanded ? 'bg-terminal-surface/30' : ''
      }`}
    >
      <td className="px-2 py-2 text-terminal-muted">{trade.rank}</td>
      <td className="px-2 py-2 font-bold text-terminal-cyan">{trade.symbol}</td>
      <td className="px-2 py-2">${trade.strike.toFixed(0)}</td>
      <td className="px-2 py-2">{trade.days_to_expiry}d</td>
      <td className="px-2 py-2 text-terminal-green">${trade.premium.toFixed(2)}</td>
      <td className="px-2 py-2"><POPBar value={trade.pop} /></td>
      {/* Desktop-only columns */}
      <td className="px-2 py-2 hidden md:table-cell">{trade.delta.toFixed(2)}</td>
      <td className="px-2 py-2 hidden md:table-cell">
        {trade.theta !== null ? `$${trade.theta.toFixed(3)}` : '--'}
      </td>
      <td className="px-2 py-2 hidden md:table-cell">
        {(trade.implied_volatility * 100).toFixed(0)}%
      </td>
      <td className="px-2 py-2 hidden md:table-cell">
        <span className={trade.expected_value >= 0 ? 'text-terminal-green' : 'text-terminal-red'}>
          ${trade.expected_value.toFixed(0)}
        </span>
      </td>
      <td className="px-2 py-2"><SafetyBar value={trade.safety_score} /></td>
      <td className="px-2 py-2 hidden md:table-cell text-terminal-yellow">
        {trade.adjusted_score !== null ? trade.adjusted_score.toFixed(0) : '--'}
      </td>
    </tr>
  )
}
