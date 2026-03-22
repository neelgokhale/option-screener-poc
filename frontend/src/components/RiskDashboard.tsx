import { useEffect } from 'react'
import type { MarketRiskStatus } from '../types'

interface Props {
  status: MarketRiskStatus | null
  loading: boolean
  onRefresh: () => void
  onClose: () => void
}

export default function RiskDashboard({ status, loading, onRefresh, onClose }: Props) {
  useEffect(() => {
    onRefresh()
  }, [onRefresh])

  return (
    <div className="border-b border-terminal-border bg-terminal-surface/80 px-4 py-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-terminal-cyan uppercase tracking-wider">Market Risk</h3>
        <button
          onClick={onClose}
          className="text-terminal-muted hover:text-terminal-text text-sm"
        >
          Close
        </button>
      </div>

      {loading && !status && (
        <p className="text-sm text-terminal-muted">Loading market data...</p>
      )}

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-terminal-muted block text-xs">VIX</span>
            <span className={`text-lg font-bold ${status.vix_level > status.vix_threshold ? 'text-terminal-red' : 'text-terminal-green'}`}>
              {status.vix_level.toFixed(1)}
            </span>
            <span className="text-terminal-muted text-xs ml-1">(threshold: {status.vix_threshold})</span>
          </div>

          <div>
            <span className="text-terminal-muted block text-xs">SPY</span>
            <span className="text-lg font-bold">${status.spy_price.toFixed(2)}</span>
          </div>

          <div>
            <span className="text-terminal-muted block text-xs">SPY 20d SMA</span>
            <span className="text-lg font-bold">${status.spy_sma_20.toFixed(2)}</span>
            <span className={`text-xs ml-1 ${status.spy_above_sma ? 'text-terminal-green' : 'text-terminal-red'}`}>
              {status.spy_above_sma ? 'Above' : 'Below'}
            </span>
          </div>

          <div>
            <span className="text-terminal-muted block text-xs">Status</span>
            {status.risk_elevated ? (
              <span className="inline-block mt-1 px-2 py-0.5 bg-terminal-red/20 text-terminal-red border border-terminal-red/30 rounded text-xs font-bold uppercase">
                Elevated Risk
              </span>
            ) : (
              <span className="inline-block mt-1 px-2 py-0.5 bg-terminal-green/20 text-terminal-green border border-terminal-green/30 rounded text-xs font-bold uppercase">
                Normal
              </span>
            )}
            {status.risk_reason && (
              <span className="block text-xs text-terminal-muted mt-1">{status.risk_reason}</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
