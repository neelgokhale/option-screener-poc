import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { EquityCurvePoint } from '../types'

interface Props {
  data: EquityCurvePoint[]
}

export default function EquityCurve({ data }: Props) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="scan_date" tick={{ fontSize: 11 }} stroke="#888" />
          <YAxis tick={{ fontSize: 11 }} stroke="#888" tickFormatter={(v) => `${v.toFixed(1)}%`} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #333' }}
            formatter={(value: number) => [`${value.toFixed(2)}%`, 'Cumulative P&L']}
          />
          <Line
            type="monotone"
            dataKey="cumulative_pnl_pct"
            stroke="#4ade80"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
