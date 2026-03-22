import type { TradeOutput } from '../types'

interface Props {
  trade: TradeOutput
}

export default function TradeDetail({ trade }: Props) {
  const evBreakdown = {
    profitSide: trade.pop * trade.premium * 100,
    lossSide: (1 - trade.pop) * (trade.strike - trade.support_level) * 100,
  }

  return (
    <div className="bg-terminal-bg/50 border-t border-terminal-border px-4 py-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
        {/* Greeks */}
        <div>
          <h4 className="text-terminal-cyan text-xs mb-2 uppercase tracking-wider">Greeks</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-terminal-muted">Delta</span>
              <span>{trade.delta.toFixed(3)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-terminal-muted">Theta</span>
              <span>{trade.theta !== null ? `$${trade.theta.toFixed(3)}` : '--'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-terminal-muted">IV</span>
              <span>{(trade.implied_volatility * 100).toFixed(1)}%</span>
            </div>
          </div>
        </div>

        {/* EV Breakdown */}
        <div>
          <h4 className="text-terminal-cyan text-xs mb-2 uppercase tracking-wider">EV Breakdown</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-terminal-muted">POP x Premium</span>
              <span className="text-terminal-green">${evBreakdown.profitSide.toFixed(0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-terminal-muted">(1-POP) x Loss</span>
              <span className="text-terminal-red">-${evBreakdown.lossSide.toFixed(0)}</span>
            </div>
            <div className="flex justify-between border-t border-terminal-border pt-1">
              <span className="text-terminal-muted">Net EV</span>
              <span className={trade.expected_value >= 0 ? 'text-terminal-green' : 'text-terminal-red'}>
                ${trade.expected_value.toFixed(0)}
              </span>
            </div>
          </div>
        </div>

        {/* Position Context */}
        <div>
          <h4 className="text-terminal-cyan text-xs mb-2 uppercase tracking-wider">Position</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-terminal-muted">Price</span>
              <span>${trade.current_price.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-terminal-muted">Support</span>
              <span>${trade.support_level.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-terminal-muted">Strike vs Price</span>
              <span>{(((trade.current_price - trade.strike) / trade.current_price) * 100).toFixed(1)}% OTM</span>
            </div>
            <div className="flex justify-between">
              <span className="text-terminal-muted">Earnings</span>
              <span>{trade.next_earnings ?? 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
