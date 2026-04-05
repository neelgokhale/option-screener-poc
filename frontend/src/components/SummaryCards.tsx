import Tooltip from './Tooltip'
import type { SummaryResponse } from '../types'

interface Props {
  summary: SummaryResponse
}

function formatPct(val: number | null): string {
  if (val === null) return '—'
  return `${val.toFixed(2)}%`
}

function formatHitRate(val: number | null): string {
  if (val === null) return '—'
  return `${(val * 100).toFixed(1)}%`
}

function formatRatio(val: number | null): string {
  if (val === null) return '—'
  return val.toFixed(2)
}

const TOOLTIPS: Record<string, string> = {
  'Total Tracked': 'Total number of trades captured by daily snapshots',
  'Resolved': 'Trades that have reached expiry and been settled',
  'Active': 'Trades awaiting expiry, still being tracked',
  'Hit Rate': 'Percentage of resolved trades that expired OTM (profitable)',
  'Avg Return': 'Average P&L percentage across all resolved trades',
  'Avg Win': 'Average P&L percentage for winning (OTM) trades',
  'Avg Loss': 'Average P&L percentage for losing (ITM) trades',
  'Win/Loss Ratio': 'Ratio of average win size to average loss size',
}

export default function SummaryCards({ summary }: Props) {
  const cards = [
    { label: 'Total Tracked', value: String(summary.total_tracked) },
    { label: 'Resolved', value: String(summary.total_resolved) },
    { label: 'Active', value: String(summary.total_active) },
    { label: 'Hit Rate', value: formatHitRate(summary.hit_rate) },
    { label: 'Avg Return', value: formatPct(summary.avg_return_pct) },
    { label: 'Avg Win', value: formatPct(summary.avg_win_pct) },
    { label: 'Avg Loss', value: formatPct(summary.avg_loss_pct) },
    { label: 'Win/Loss Ratio', value: formatRatio(summary.win_loss_ratio) },
  ]

  return (
    <div>
      <div className="grid grid-cols-4 gap-3 mb-4">
        {cards.map((c) => (
          <div
            key={c.label}
            className="bg-terminal-surface border border-terminal-border rounded p-3"
          >
            <Tooltip text={TOOLTIPS[c.label]}>
              <div className="text-xs text-terminal-muted mb-1">{c.label}</div>
            </Tooltip>
            <div className="text-lg font-bold">{c.value}</div>
          </div>
        ))}
      </div>
      {summary.date_range_start && summary.date_range_end && (
        <div className="text-xs text-terminal-muted">
          Date range: {summary.date_range_start} — {summary.date_range_end}
        </div>
      )}
    </div>
  )
}
