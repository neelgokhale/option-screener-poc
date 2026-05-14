import { useState } from 'react'

export default function MethodologyPanel() {
  const [open, setOpen] = useState(false)

  return (
    <section className="mt-6">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-bold text-terminal-muted hover:text-terminal-text transition-colors"
      >
        <span>{open ? '▾' : '▸'}</span>
        Methodology
      </button>

      {open && (
        <div className="mt-3 bg-terminal-surface border border-terminal-border rounded p-4 text-sm space-y-4">
          <div>
            <h3 className="font-bold text-terminal-cyan mb-1">Outcome Determination</h3>
            <p className="text-terminal-muted">
              Each trade is resolved at expiry. The settlement price is compared to the strike price
              to determine the outcome.
            </p>
          </div>

          <div>
            <h3 className="font-bold text-terminal-cyan mb-1">OTM (Out of the Money)</h3>
            <p className="text-terminal-muted">
              A put option expires OTM when the underlying stock price is above the strike price at expiry.
              This is a winning trade — the seller keeps the full premium.
            </p>
          </div>

          <div>
            <h3 className="font-bold text-terminal-cyan mb-1">ITM (In the Money)</h3>
            <p className="text-terminal-muted">
              A put option expires ITM when the underlying stock price is below the strike price at expiry.
              The seller is assigned shares and incurs a loss equal to (strike − settlement price − premium received).
            </p>
          </div>

          <div>
            <h3 className="font-bold text-terminal-cyan mb-1">P&L Calculation</h3>
            <p className="text-terminal-muted">
              For OTM trades: P&L % = premium / (strike × margin requirement) × 100.
              For ITM trades: P&L % = (premium − (strike − settlement price)) / (strike × margin requirement) × 100.
            </p>
          </div>

          <div>
            <h3 className="font-bold text-terminal-cyan mb-1">Hit Rate</h3>
            <p className="text-terminal-muted">
              Percentage of resolved trades that expired OTM (profitable). Hit rate = OTM trades / total resolved trades.
            </p>
          </div>

          <div>
            <h3 className="font-bold text-terminal-cyan mb-1">Timing Assumptions</h3>
            <p className="text-terminal-muted">
              Trades are tracked from the daily snapshot. Resolution uses next-day closing prices after expiry.
              Settlement prices are fetched from market data on the first trading day after expiration.
            </p>
          </div>

          <div>
            <h3 className="font-bold text-terminal-cyan mb-1">Scoring</h3>
            <p className="text-terminal-muted">
              Safety Score combines POP, delta, support proximity, and implied volatility.
              Adjusted Score applies time-decay and earnings proximity adjustments.
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
