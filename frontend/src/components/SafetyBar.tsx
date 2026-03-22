interface Props {
  value: number | null // 0-1
}

export default function SafetyBar({ value }: Props) {
  if (value === null) {
    return <span className="text-xs text-terminal-muted">--</span>
  }

  const pct = Math.round(value * 100)
  const color =
    value >= 0.20 ? 'bg-terminal-green' :
    value >= 0.10 ? 'bg-terminal-yellow' :
    'bg-terminal-red'

  return (
    <div className="flex items-center gap-1.5 min-w-[70px]">
      <div className="flex-1 h-3 bg-terminal-bg rounded overflow-hidden">
        <div
          className={`h-full ${color} rounded transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs w-8 text-right">{value.toFixed(2)}</span>
    </div>
  )
}
