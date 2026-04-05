import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

vi.mock('../hooks/useTrades', () => ({
  useTrades: () => ({ scanResult: null, loading: false, error: null, runScan: vi.fn() }),
  useMarketStatus: () => ({ status: null, loading: false, refresh: vi.fn() }),
}))

vi.mock('../api/client', () => ({
  fetchReportSummary: vi.fn().mockResolvedValue({
    total_tracked: 0, total_resolved: 0, total_active: 0,
    hit_rate: null, avg_return_pct: null, avg_win_pct: null,
    avg_loss_pct: null, win_loss_ratio: null,
    date_range_start: null, date_range_end: null,
  }),
  fetchReportTrades: vi.fn().mockResolvedValue({ trades: [] }),
}))

function renderApp(route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  )
}

describe('Routing', () => {
  it('renders the screener at /', () => {
    renderApp('/')
    expect(screen.getByText('OptionTerminal')).toBeInTheDocument()
  })

  it('renders the report page at /report', async () => {
    renderApp('/report')
    expect(await screen.findByText('Backtesting Report')).toBeInTheDocument()
  })
})

describe('NavBar', () => {
  it('shows nav links on the screener page', () => {
    renderApp('/')
    expect(screen.getByRole('link', { name: /screener/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /report/i })).toBeInTheDocument()
  })

  it('shows nav links on the report page', () => {
    renderApp('/report')
    expect(screen.getByRole('link', { name: /screener/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /report/i })).toBeInTheDocument()
  })

  it('navigates from screener to report', async () => {
    renderApp('/')
    await userEvent.click(screen.getByRole('link', { name: /report/i }))
    expect(await screen.findByText('Backtesting Report')).toBeInTheDocument()
  })

  it('navigates from report to screener', async () => {
    renderApp('/report')
    await userEvent.click(screen.getByRole('link', { name: /screener/i }))
    expect(screen.getByText('Run Scanner')).toBeInTheDocument()
  })
})

describe('SummaryCards', () => {
  it('displays all summary metrics from API', async () => {
    const { fetchReportSummary } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValueOnce({
      total_tracked: 42,
      total_resolved: 30,
      total_active: 12,
      hit_rate: 0.733,
      avg_return_pct: 2.15,
      avg_win_pct: 3.5,
      avg_loss_pct: -1.8,
      win_loss_ratio: 1.94,
      date_range_start: '2026-01-15',
      date_range_end: '2026-04-01',
    })

    renderApp('/report')

    expect(await screen.findByText('42')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('73.3%')).toBeInTheDocument()
    expect(screen.getByText('2.15%')).toBeInTheDocument()
    expect(screen.getByText('3.50%')).toBeInTheDocument()
    expect(screen.getByText('-1.80%')).toBeInTheDocument()
    expect(screen.getByText('1.94')).toBeInTheDocument()
    expect(screen.getByText(/2026-01-15/)).toBeInTheDocument()
    expect(screen.getByText(/2026-04-01/)).toBeInTheDocument()
  })

  it('shows empty state when total_tracked is zero', async () => {
    const { fetchReportSummary } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValueOnce({
      total_tracked: 0, total_resolved: 0, total_active: 0,
      hit_rate: null, avg_return_pct: null, avg_win_pct: null,
      avg_loss_pct: null, win_loss_ratio: null,
      date_range_start: null, date_range_end: null,
    })

    renderApp('/report')
    expect(await screen.findByText(/no trades tracked yet/i)).toBeInTheDocument()
  })
})

const MOCK_SUMMARY_WITH_DATA = {
  total_tracked: 5, total_resolved: 3, total_active: 2,
  hit_rate: 0.6, avg_return_pct: 1.5, avg_win_pct: 3.0,
  avg_loss_pct: -2.0, win_loss_ratio: 1.5,
  date_range_start: '2026-01-01', date_range_end: '2026-04-01',
}

const MOCK_ACTIVE_TRADE = {
  id: 1, snapshot_id: 1, snapshot_date: '2026-03-01', rank: 1,
  symbol: 'AAPL', expiry: '2026-04-18', strike: 170, premium: 2.5,
  pop: 0.72, delta: -0.28, theta: 0.05, implied_volatility: 0.32,
  expected_value: 1.8, days_to_expiry: 48, support_level: 168,
  current_price: 178.5, premium_yield: 1.47, open_interest: 1200,
  safety_score: 82, adjusted_score: 78, next_earnings: '2026-05-01',
  outcome: null, settlement_price: null, pnl_pct: null, days_remaining: 13,
}

describe('ActiveTradesTable', () => {
  it('renders active trades with DTE, price, and strike', async () => {
    const { fetchReportSummary, fetchReportTrades } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValueOnce(MOCK_SUMMARY_WITH_DATA)
    fetchReportTrades.mockResolvedValueOnce({ trades: [MOCK_ACTIVE_TRADE] })

    renderApp('/report')

    expect(await screen.findByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('170')).toBeInTheDocument()
    expect(screen.getByText('178.5')).toBeInTheDocument()
    expect(screen.getByText('13d')).toBeInTheDocument()
  })
})

const MOCK_RESOLVED_TRADE = {
  id: 2, snapshot_id: 1, snapshot_date: '2026-02-01', rank: 3,
  symbol: 'MSFT', expiry: '2026-03-21', strike: 400, premium: 5.0,
  pop: 0.68, delta: -0.32, theta: 0.04, implied_volatility: 0.28,
  expected_value: 3.4, days_to_expiry: 48, support_level: 395,
  current_price: 410, premium_yield: 1.25, open_interest: 800,
  safety_score: 75, adjusted_score: 71, next_earnings: null,
  outcome: 'OTM', settlement_price: 405.0, pnl_pct: 1.25, days_remaining: null,
}

describe('ResolvedTradesTable', () => {
  it('renders resolved trades with outcome, settlement price, P&L, and scores', async () => {
    const { fetchReportSummary, fetchReportTrades } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValueOnce(MOCK_SUMMARY_WITH_DATA)
    fetchReportTrades.mockResolvedValueOnce({ trades: [MOCK_RESOLVED_TRADE] })

    renderApp('/report')

    expect(await screen.findByText('MSFT')).toBeInTheDocument()
    expect(screen.getByText('OTM')).toBeInTheDocument()
    expect(screen.getByText('405')).toBeInTheDocument()
    expect(screen.getByText('+1.25%')).toBeInTheDocument()
    expect(screen.getByText('75')).toBeInTheDocument()
  })
})

describe('StatusFilter', () => {
  it('re-fetches trades when filter changes', async () => {
    const { fetchReportSummary, fetchReportTrades } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValue(MOCK_SUMMARY_WITH_DATA)
    fetchReportTrades
      .mockResolvedValueOnce({ trades: [MOCK_ACTIVE_TRADE, MOCK_RESOLVED_TRADE] })
      .mockResolvedValueOnce({ trades: [MOCK_ACTIVE_TRADE] })

    renderApp('/report')

    // Wait for initial load
    expect(await screen.findByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()

    // Click "Active" filter
    await userEvent.click(screen.getByRole('button', { name: /^active$/i }))

    // Should have re-fetched with status=active
    expect(fetchReportTrades).toHaveBeenLastCalledWith('active')
  })
})

describe('RefreshPrices', () => {
  it('calls fetchReportTrades when refresh prices button is clicked', async () => {
    const { fetchReportSummary, fetchReportTrades } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValue(MOCK_SUMMARY_WITH_DATA)
    fetchReportTrades
      .mockResolvedValueOnce({ trades: [MOCK_ACTIVE_TRADE] })
      .mockResolvedValueOnce({ trades: [{ ...MOCK_ACTIVE_TRADE, current_price: 180.0 }] })

    renderApp('/report')
    expect(await screen.findByText('AAPL')).toBeInTheDocument()

    const callCountBefore = fetchReportTrades.mock.calls.length
    await userEvent.click(screen.getByRole('button', { name: /refresh prices/i }))
    expect(fetchReportTrades.mock.calls.length).toBeGreaterThan(callCountBefore)
  })
})

describe('MethodologyPanel', () => {
  it('is collapsed by default and expands on click', async () => {
    const { fetchReportSummary, fetchReportTrades } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValue(MOCK_SUMMARY_WITH_DATA)
    fetchReportTrades.mockResolvedValue({ trades: [MOCK_ACTIVE_TRADE] })

    renderApp('/report')
    expect(await screen.findByText('AAPL')).toBeInTheDocument()

    // Panel content should not be visible initially
    expect(screen.queryByText(/OTM \(Out of the Money\)/i)).not.toBeInTheDocument()

    // Click to expand
    await userEvent.click(screen.getByRole('button', { name: /methodology/i }))
    expect(screen.getByText(/OTM \(Out of the Money\)/i)).toBeInTheDocument()

    // Click to collapse
    await userEvent.click(screen.getByRole('button', { name: /methodology/i }))
    expect(screen.queryByText(/OTM \(Out of the Money\)/i)).not.toBeInTheDocument()
  })
})

describe('Tooltips', () => {
  it('summary card labels have tooltip text', async () => {
    const { fetchReportSummary, fetchReportTrades } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValue(MOCK_SUMMARY_WITH_DATA)
    fetchReportTrades.mockResolvedValue({ trades: [MOCK_ACTIVE_TRADE] })

    renderApp('/report')
    expect(await screen.findByText('AAPL')).toBeInTheDocument()

    // Hover over "Hit Rate" label to reveal tooltip
    const hitRateLabel = screen.getByText('Hit Rate')
    await userEvent.hover(hitRateLabel)
    expect(await screen.findByText(/percentage of resolved trades that expired OTM/i)).toBeInTheDocument()
  })
})

describe('EmptyTables', () => {
  it('shows empty state messages when no trades exist', async () => {
    const { fetchReportSummary, fetchReportTrades } = await import('../api/client') as any
    fetchReportSummary.mockResolvedValueOnce({
      ...MOCK_SUMMARY_WITH_DATA,
      total_tracked: 1,
    })
    fetchReportTrades.mockResolvedValueOnce({ trades: [] })

    renderApp('/report')

    expect(await screen.findByText(/no active trades/i)).toBeInTheDocument()
    expect(screen.getByText(/no resolved trades/i)).toBeInTheDocument()
  })
})
