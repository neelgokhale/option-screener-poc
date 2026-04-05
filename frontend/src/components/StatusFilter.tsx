interface Props {
  value: string
  onChange: (status: string) => void
}

const OPTIONS = ['all', 'active', 'resolved'] as const

export default function StatusFilter({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {OPTIONS.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={`px-3 py-1 rounded text-sm capitalize transition-colors ${
            value === opt
              ? 'bg-terminal-cyan/20 text-terminal-cyan border border-terminal-cyan/30'
              : 'text-terminal-muted hover:text-terminal-text border border-terminal-border'
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
