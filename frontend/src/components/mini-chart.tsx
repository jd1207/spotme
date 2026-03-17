import type { TrendPoint } from '../types'

interface MiniChartProps {
  data: TrendPoint[]
  valueKey: string
  label: string
  unit: string
  color: string
}

export function MiniChart({ data, valueKey, label, unit, color }: MiniChartProps) {
  if (data.length === 0) return null

  const values = data.map(d => (d[valueKey] as number) || 0)
  const max = Math.max(...values, 1)

  return (
    <div className="progress-chart">
      <span className="progress-chart-label">{label}</span>
      <div className="progress-bars">
        {data.map((d, i) => (
          <div
            key={i}
            className="progress-bar-col"
            title={`${d.date}: ${values[i]}${unit}`}
          >
            <div
              className="progress-bar"
              style={{
                height: `${(values[i] / max) * 100}%`,
                background: color,
              }}
            />
          </div>
        ))}
      </div>
      <div className="progress-chart-footer">
        <span>Latest: {values[values.length - 1]}{unit}</span>
        <span>Peak: {Math.max(...values)}{unit}</span>
      </div>
    </div>
  )
}
