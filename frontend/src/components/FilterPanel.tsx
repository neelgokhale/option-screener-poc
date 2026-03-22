export interface Filters {
  minPop: number
  minSafety: number
  minExpiry: number
  maxExpiry: number
  minYield: number
}

export const DEFAULT_FILTERS: Filters = {
  minPop: 0.70,
  minSafety: 0,
  minExpiry: 14,
  maxExpiry: 21,
  minYield: 0.005,
}

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
}

export default function FilterPanel({ filters, onChange }: Props) {
  const set = (key: keyof Filters, value: number) =>
    onChange({ ...filters, [key]: value })

  return (
    <div className="border-b border-terminal-border bg-terminal-surface/50 px-4 py-3">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-terminal-muted">Min POP</span>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={50}
              max={95}
              value={filters.minPop * 100}
              onChange={(e) => set('minPop', Number(e.target.value) / 100)}
              className="flex-1"
            />
            <span className="w-10 text-right">{Math.round(filters.minPop * 100)}%</span>
          </div>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-terminal-muted">Min Safety</span>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={0}
              max={50}
              value={filters.minSafety * 100}
              onChange={(e) => set('minSafety', Number(e.target.value) / 100)}
              className="flex-1"
            />
            <span className="w-10 text-right">{filters.minSafety.toFixed(2)}</span>
          </div>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-terminal-muted">Expiry (days)</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              min={7}
              max={60}
              value={filters.minExpiry}
              onChange={(e) => set('minExpiry', Number(e.target.value))}
              className="w-14 bg-terminal-bg border border-terminal-border rounded px-1 py-0.5 text-terminal-text"
            />
            <span>-</span>
            <input
              type="number"
              min={7}
              max={60}
              value={filters.maxExpiry}
              onChange={(e) => set('maxExpiry', Number(e.target.value))}
              className="w-14 bg-terminal-bg border border-terminal-border rounded px-1 py-0.5 text-terminal-text"
            />
          </div>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-terminal-muted">Min Yield</span>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={0}
              max={5}
              step={0.1}
              value={filters.minYield * 100}
              onChange={(e) => set('minYield', Number(e.target.value) / 100)}
              className="flex-1"
            />
            <span className="w-10 text-right">{(filters.minYield * 100).toFixed(1)}%</span>
          </div>
        </label>
      </div>
    </div>
  )
}
