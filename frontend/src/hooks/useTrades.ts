import { useState, useCallback } from 'react'
import type { ScanResult, MarketRiskStatus } from '../types'
import { fetchTrades, fetchMarketStatus } from '../api/client'

export function useTrades() {
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runScan = useCallback(async (symbols?: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchTrades(symbols)
      setScanResult(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Scan failed')
    } finally {
      setLoading(false)
    }
  }, [])

  return { scanResult, loading, error, runScan }
}

export function useMarketStatus() {
  const [status, setStatus] = useState<MarketRiskStatus | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const result = await fetchMarketStatus()
      setStatus(result)
    } catch {
      // silently fail — market status is non-critical
    } finally {
      setLoading(false)
    }
  }, [])

  return { status, loading, refresh }
}
