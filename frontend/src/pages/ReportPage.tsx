import { useState, useEffect, useCallback } from 'react'
import { fetchBacktestRuns, fetchReportSummary, fetchReportTrades, fetchEquityCurve } from '../api/client'
import ActiveTradesTable from '../components/ActiveTradesTable'
import BacktestRunSelector from '../components/BacktestRunSelector'
import EquityCurve from '../components/EquityCurve'
import MethodologyPanel from '../components/MethodologyPanel'
import ResolvedTradesTable from '../components/ResolvedTradesTable'
import StatusFilter from '../components/StatusFilter'
import SummaryCards from '../components/SummaryCards'
import type { SummaryResponse, ReportTradeItem, BacktestRun, EquityCurvePoint } from '../types'

export default function ReportPage() {
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [trades, setTrades] = useState<ReportTradeItem[]>([])
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(true)
  const [runs, setRuns] = useState<BacktestRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
  const [equityCurve, setEquityCurve] = useState<EquityCurvePoint[]>([])

  const loadData = useCallback(async (s: string, runId: number | null) => {
    const [summaryData, tradesData, curveData] = await Promise.all([
      fetchReportSummary(runId),
      fetchReportTrades(s, runId),
      fetchEquityCurve(runId),
    ])
    setSummary(summaryData)
    setTrades(tradesData.trades)
    setEquityCurve(curveData)
  }, [])

  useEffect(() => {
    async function load() {
      setLoading(true)
      const runsData = await fetchBacktestRuns()
      setRuns(runsData)
      await loadData(status, selectedRunId)
      setLoading(false)
    }
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRunChange = async (runId: number | null) => {
    setSelectedRunId(runId)
    await loadData(status, runId)
  }

  const handleStatusChange = async (newStatus: string) => {
    setStatus(newStatus)
    const tradesData = await fetchReportTrades(newStatus, selectedRunId)
    setTrades(tradesData.trades)
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
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">Backtesting Report</h1>
          <BacktestRunSelector runs={runs} selectedRunId={selectedRunId} onChange={handleRunChange} />
        </div>
        <StatusFilter value={status} onChange={handleStatusChange} />
      </div>

      {summary && <SummaryCards summary={summary} />}

      {equityCurve.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-bold text-terminal-muted mb-2">Equity Curve</h2>
          <EquityCurve data={equityCurve} />
        </section>
      )}

      <section className="mt-6">
        <h2 className="text-sm font-bold text-terminal-muted mb-2">Active Trades</h2>
        <ActiveTradesTable trades={activeTrades} onRefresh={() => handleStatusChange(status)} />
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-bold text-terminal-muted mb-2">Resolved Trades</h2>
        <ResolvedTradesTable trades={resolvedTrades} />
      </section>

      <MethodologyPanel />
    </div>
  )
}
