import { useState } from 'react'

interface Props {
  capital: number
  margin: number
  onCapitalChange: (v: number) => void
  onMarginChange: (v: number) => void
}

export default function CapitalSettings({ capital, margin, onCapitalChange, onMarginChange }: Props) {
  const [editing, setEditing] = useState(false)

  return (
    <div className="border-b border-terminal-border bg-terminal-surface px-4 py-2 flex items-center gap-4 text-sm text-terminal-muted">
      {editing ? (
        <div className="flex items-center gap-2">
          <label>
            Capital:
            <input
              type="number"
              value={capital}
              onChange={(e) => onCapitalChange(Number(e.target.value))}
              className="ml-1 w-24 bg-terminal-bg border border-terminal-border rounded px-2 py-0.5 text-terminal-text text-sm"
            />
          </label>
          <label>
            Margin:
            <input
              type="number"
              value={Math.round(margin * 100)}
              onChange={(e) => onMarginChange(Number(e.target.value) / 100)}
              className="ml-1 w-16 bg-terminal-bg border border-terminal-border rounded px-2 py-0.5 text-terminal-text text-sm"
            />%
          </label>
          <button
            onClick={() => setEditing(false)}
            className="text-terminal-green hover:text-terminal-text"
          >
            Done
          </button>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="flex items-center gap-3 hover:text-terminal-text transition-colors"
        >
          <span>Capital: <span className="text-terminal-text">${capital.toLocaleString()}</span></span>
          <span>Margin: <span className="text-terminal-text">{Math.round(margin * 100)}%</span></span>
        </button>
      )}
    </div>
  )
}
