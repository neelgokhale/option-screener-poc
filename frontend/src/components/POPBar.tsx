interface Props {
  value: number // 0-1
}

export default function POPBar({ value }: Props) {
  const pct = Math.round(value * 100)
  const color =
    pct >= 75 ? 'bg-terminal-green' :
    pct >= 60 ? 'bg-terminal-yellow' :
    'bg-terminal-red'

  return (
    <div className="flex items-center gap-1.5 min-w-[80px]">
      <div className="flex-1 h-3 bg-terminal-bg rounded overflow-hidden">
        <div
          className={`h-full ${color} rounded transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs w-8 text-right">{pct}%</span>
    </div>
  )
}
