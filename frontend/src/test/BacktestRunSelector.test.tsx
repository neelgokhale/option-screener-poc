import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BacktestRunSelector from '../components/BacktestRunSelector'

const MOCK_RUNS = [
  {
    id: 2,
    name: 'run-beta',
    started_at: '2026-04-15T08:00:00+00:00',
    completed_at: '2026-04-15T09:00:00+00:00',
    date_range_start: '2025-07-01',
    date_range_end: '2025-12-31',
    total_trades: 15,
  },
  {
    id: 1,
    name: 'run-alpha',
    started_at: '2026-03-01T10:00:00+00:00',
    completed_at: '2026-03-01T11:00:00+00:00',
    date_range_start: '2025-01-01',
    date_range_end: '2025-06-30',
    total_trades: 10,
  },
]

describe('BacktestRunSelector', () => {
  it('renders a Live option and all runs', async () => {
    const onChange = vi.fn()
    render(
      <BacktestRunSelector runs={MOCK_RUNS} selectedRunId={null} onChange={onChange} />,
    )

    const select = screen.getByRole('combobox')
    expect(select).toBeInTheDocument()

    await userEvent.click(select)
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(3)
    expect(options[0]).toHaveTextContent('Live')
    expect(options[1]).toHaveTextContent('run-beta')
    expect(options[2]).toHaveTextContent('run-alpha')
  })

  it('calls onChange with run id when a run is selected', async () => {
    const onChange = vi.fn()
    render(
      <BacktestRunSelector runs={MOCK_RUNS} selectedRunId={null} onChange={onChange} />,
    )

    await userEvent.selectOptions(screen.getByRole('combobox'), '2')
    expect(onChange).toHaveBeenCalledWith(2)
  })

  it('calls onChange with null when Live is selected', async () => {
    const onChange = vi.fn()
    render(
      <BacktestRunSelector runs={MOCK_RUNS} selectedRunId={2} onChange={onChange} />,
    )

    await userEvent.selectOptions(screen.getByRole('combobox'), '')
    expect(onChange).toHaveBeenCalledWith(null)
  })
})
