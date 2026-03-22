import { useState, useEffect } from 'react'
import AppHeader from './components/AppHeader'
import ControlBar from './components/ControlBar'
import FilterPanel, { DEFAULT_FILTERS, type Filters } from './components/FilterPanel'
import RiskDashboard from './components/RiskDashboard'
import TradeTable from './components/TradeTable'
import { useTrades, useMarketStatus } from './hooks/useTrades'

function App() {
  const [capital, setCapital] = useState(() => {
    const saved = localStorage.getItem('capital')
    return saved ? Number(saved) : 50000
  })
  const [margin, setMargin] = useState(() => {
    const saved = localStorage.getItem('margin')
    return saved ? Number(saved) : 0.3
  })
  const [filterOpen, setFilterOpen] = useState(false)
  const [riskOpen, setRiskOpen] = useState(false)
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)

  const { scanResult, loading, error, runScan } = useTrades()
  const { status: marketStatus, loading: marketLoading, refresh: refreshMarket } = useMarketStatus()

  useEffect(() => {
    localStorage.setItem('capital', String(capital))
  }, [capital])

  useEffect(() => {
    localStorage.setItem('margin', String(margin))
  }, [margin])

  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader
        capital={capital}
        margin={margin}
        onCapitalChange={setCapital}
        onMarginChange={setMargin}
      />

      <ControlBar
        onScan={() => runScan()}
        onToggleFilter={() => setFilterOpen(!filterOpen)}
        onToggleRisk={() => setRiskOpen(!riskOpen)}
        loading={loading}
        filterOpen={filterOpen}
      />

      {riskOpen && (
        <RiskDashboard
          status={marketStatus}
          loading={marketLoading}
          onRefresh={refreshMarket}
          onClose={() => setRiskOpen(false)}
        />
      )}

      {filterOpen && (
        <FilterPanel filters={filters} onChange={setFilters} />
      )}

      {error && (
        <div className="px-4 py-2 bg-terminal-red/10 border-b border-terminal-red/30 text-terminal-red text-sm">
          {error}
        </div>
      )}

      {scanResult && (
        <div className="px-4 py-2 border-b border-terminal-border text-xs text-terminal-muted flex gap-4">
          <span>Universe: {scanResult.universe_size}</span>
          <span>Qualified: {scanResult.qualified_stocks}</span>
          <span>Trades: {scanResult.trades_screened}</span>
          <span>Scanned: {scanResult.scan_timestamp}</span>
        </div>
      )}

      <TradeTable
        trades={scanResult?.trades ?? []}
        filters={filters}
      />
    </div>
  )
}

export default App
