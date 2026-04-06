export interface TradeOutput {
  rank: number
  symbol: string
  expiry: string
  strike: number
  premium: number
  pop: number
  delta: number
  theta: number | null
  implied_volatility: number
  expected_value: number
  days_to_expiry: number
  support_level: number
  current_price: number
  premium_yield: number
  open_interest: number
  safety_score: number | null
  adjusted_score: number | null
  next_earnings: string | null
}

export interface ScanResult {
  trades: TradeOutput[]
  universe_size: number
  qualified_stocks: number
  trades_screened: number
  scan_timestamp: string
}

export interface SummaryResponse {
  total_tracked: number
  total_resolved: number
  total_active: number
  hit_rate: number | null
  avg_return_pct: number | null
  avg_win_pct: number | null
  avg_loss_pct: number | null
  win_loss_ratio: number | null
  date_range_start: string | null
  date_range_end: string | null
}

export interface ReportTradeItem {
  id: number
  snapshot_id: number
  snapshot_date: string
  rank: number
  symbol: string
  expiry: string
  strike: number
  premium: number
  pop: number
  delta: number
  theta: number | null
  implied_volatility: number
  expected_value: number
  days_to_expiry: number
  support_level: number
  current_price: number
  premium_yield: number
  open_interest: number
  safety_score: number | null
  adjusted_score: number | null
  next_earnings: string | null
  outcome: string | null
  settlement_price: number | null
  pnl_pct: number | null
  days_remaining: number | null
}

export interface TradesResponse {
  trades: ReportTradeItem[]
}

export interface MarketRiskStatus {
  vix_level: number
  vix_threshold: number
  spy_price: number
  spy_sma_20: number
  spy_above_sma: boolean
  risk_elevated: boolean
  risk_reason: string | null
}
