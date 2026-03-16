export function StatCard({ label, value, trend }: { label: string; value: string; trend?: string }) {
  return (
    <div className="stat-card">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
      {trend && <span className="trend">{trend}</span>}
    </div>
  )
}
