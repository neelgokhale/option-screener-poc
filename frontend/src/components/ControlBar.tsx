interface Props {
  onScan: () => void
  onToggleFilter: () => void
  onToggleRisk: () => void
  loading: boolean
  filterOpen: boolean
}

export default function ControlBar({ onScan, onToggleFilter, onToggleRisk, loading, filterOpen }: Props) {
  return (
    <div className="border-b border-terminal-border bg-terminal-surface px-4 py-2 flex items-center gap-2 flex-wrap">
      <button
        onClick={onScan}
        disabled={loading}
        className="px-3 py-1.5 bg-terminal-green/20 text-terminal-green border border-terminal-green/30 rounded text-sm hover:bg-terminal-green/30 transition-colors disabled:opacity-50"
      >
        {loading ? 'Scanning...' : 'Run Scanner'}
      </button>

      <button
        onClick={onToggleRisk}
        className="px-3 py-1.5 bg-terminal-cyan/20 text-terminal-cyan border border-terminal-cyan/30 rounded text-sm hover:bg-terminal-cyan/30 transition-colors"
      >
        Risk Dashboard
      </button>

      <button
        onClick={onToggleFilter}
        className={`px-3 py-1.5 border rounded text-sm transition-colors ${
          filterOpen
            ? 'bg-terminal-blue/30 text-terminal-blue border-terminal-blue/30'
            : 'bg-terminal-blue/20 text-terminal-blue border-terminal-blue/30 hover:bg-terminal-blue/30'
        }`}
      >
        Filter
      </button>
    </div>
  )
}
