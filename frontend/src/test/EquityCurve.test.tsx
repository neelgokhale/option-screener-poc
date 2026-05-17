import { render } from '@testing-library/react'
import EquityCurve from '../components/EquityCurve'

const MOCK_DATA = [
  { scan_date: '2025-01-15', cumulative_pnl_pct: 1.5, trade_count: 1 },
  { scan_date: '2025-02-15', cumulative_pnl_pct: 0.7, trade_count: 1 },
  { scan_date: '2025-03-15', cumulative_pnl_pct: 2.3, trade_count: 2 },
]

describe('EquityCurve', () => {
  it('renders without crashing with data', () => {
    const { container } = render(<EquityCurve data={MOCK_DATA} />)
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })

  it('renders without crashing with empty data', () => {
    const { container } = render(<EquityCurve data={[]} />)
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })
})
