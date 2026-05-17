import type { ScanResult, MarketRiskStatus, SummaryResponse, TradesResponse, BacktestRun, EquityCurvePoint } from '../types'

// In dev: empty string → Vite proxy handles /api → localhost:8000
// In prod: VITE_API_URL points to the Railway backend (e.g. https://my-app.up.railway.app/api)
const BASE = `${import.meta.env.VITE_API_URL || ''}/api`

export async function fetchTrades(
  symbols?: string,
  maxTrades?: number,
): Promise<ScanResult> {
  const params = new URLSearchParams()
  if (symbols) params.set('symbols', symbols)
  if (maxTrades) params.set('max_trades', String(maxTrades))
  const qs = params.toString()
  const resp = await fetch(`${BASE}/trades${qs ? '?' + qs : ''}`)
  if (!resp.ok) throw new Error(`Failed to fetch trades: ${resp.status}`)
  return resp.json()
}

export async function fetchMarketStatus(): Promise<MarketRiskStatus> {
  const resp = await fetch(`${BASE}/market-status`)
  if (!resp.ok) throw new Error(`Failed to fetch market status: ${resp.status}`)
  return resp.json()
}

export async function fetchBacktestRuns(): Promise<BacktestRun[]> {
  const resp = await fetch(`${BASE}/backtest/runs`)
  if (!resp.ok) throw new Error(`Failed to fetch backtest runs: ${resp.status}`)
  return resp.json()
}

export async function fetchReportSummary(backtestRunId?: number | null): Promise<SummaryResponse> {
  const params = new URLSearchParams()
  if (backtestRunId != null) params.set('backtest_run_id', String(backtestRunId))
  const qs = params.toString()
  const resp = await fetch(`${BASE}/report/summary${qs ? '?' + qs : ''}`)
  if (!resp.ok) throw new Error(`Failed to fetch report summary: ${resp.status}`)
  return resp.json()
}

export async function fetchReportTrades(status: string = 'all', backtestRunId?: number | null): Promise<TradesResponse> {
  const params = new URLSearchParams({ status })
  if (backtestRunId != null) params.set('backtest_run_id', String(backtestRunId))
  const resp = await fetch(`${BASE}/report/trades?${params.toString()}`)
  if (!resp.ok) throw new Error(`Failed to fetch report trades: ${resp.status}`)
  return resp.json()
}

export async function fetchEquityCurve(backtestRunId?: number | null): Promise<EquityCurvePoint[]> {
  const params = new URLSearchParams()
  if (backtestRunId != null) params.set('backtest_run_id', String(backtestRunId))
  const qs = params.toString()
  const resp = await fetch(`${BASE}/report/equity-curve${qs ? '?' + qs : ''}`)
  if (!resp.ok) throw new Error(`Failed to fetch equity curve: ${resp.status}`)
  return resp.json()
}
