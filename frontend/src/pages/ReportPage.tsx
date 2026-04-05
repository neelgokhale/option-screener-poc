import { useState, useEffect, useCallback } from 'react'
import { fetchReportSummary, fetchReportTrades } from '../api/client'
import ActiveTradesTable from '../components/ActiveTradesTable'
import MethodologyPanel from '../components/MethodologyPanel'
import ResolvedTradesTable from '../components/ResolvedTradesTable'
import StatusFilter from '../components/StatusFilter'
import SummaryCards from '../components/SummaryCards'
import type { SummaryResponse, ReportTradeItem } from '../types'

export default function ReportPage() {
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [trades, setTrades] = useState<ReportTradeItem[]>([])
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(true)

  const loadTrades = useCallback(async (s: string) => {
    const t = await fetchReportTrades(s)
    setTrades(t.trades)
  }, [])

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [s] = await Promise.all([
        fetchReportSummary(),
        loadTrades(status),
      ])
      setSummary(s)
      setLoading(false)
    }
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleStatusChange = async (newStatus: string) => {
    setStatus(newStatus)
    await loadTrades(newStatus)
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-terminal-muted text-sm py-16">
        Loading report data...
      </div>
    )
  }

  if (summary && summary.total_tracked === 0) {
    return (
      <div className="flex-1 px-4 py-4">
        <h1 className="text-lg font-bold mb-4">Backtesting Report</h1>
        <div className="text-terminal-muted text-sm py-8 text-center">
          No trades tracked yet. Run the daily cron to start tracking trades.
        </div>
      </div>
    )
  }

  const activeTrades = trades.filter((t) => t.outcome === null)
  const resolvedTrades = trades.filter((t) => t.outcome !== null)

  return (
    <div className="flex-1 px-4 py-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-bold">Backtesting Report</h1>
        <StatusFilter value={status} onChange={handleStatusChange} />
      </div>

      {summary && <SummaryCards summary={summary} />}

      <section className="mt-6">
        <h2 className="text-sm font-bold text-terminal-muted mb-2">Active Trades</h2>
        <ActiveTradesTable trades={activeTrades} onRefresh={() => loadTrades(status)} />
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-bold text-terminal-muted mb-2">Resolved Trades</h2>
        <ResolvedTradesTable trades={resolvedTrades} />
      </section>

      <MethodologyPanel />
    </div>
  )
}
