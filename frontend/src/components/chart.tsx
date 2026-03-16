export function ChartComponent({ label }: { label?: string }) {
  return (
    <div className="chart-placeholder">
      <p>{label || 'Progress Chart'}</p>
    </div>
  )
}
