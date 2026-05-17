import type { BacktestRun } from '../types'

interface Props {
  runs: BacktestRun[]
  selectedRunId: number | null
  onChange: (runId: number | null) => void
}

export default function BacktestRunSelector({ runs, selectedRunId, onChange }: Props) {
  return (
    <select
      value={selectedRunId ?? ''}
      onChange={(e) => {
        const val = e.target.value
        onChange(val === '' ? null : Number(val))
      }}
      className="bg-terminal-bg border border-terminal-border text-terminal-text text-sm rounded px-2 py-1"
    >
      <option value="">Live</option>
      {runs.map((run) => (
        <option key={run.id} value={run.id}>
          {run.name}
        </option>
      ))}
    </select>
  )
}
