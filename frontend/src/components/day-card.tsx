interface DayCardProps {
  date: string
  workoutType: string | null
  recoveryZone: string | null
  caloriesTotal: number
  isToday: boolean
  onClick: () => void
}

export function DayCard({ date, workoutType, recoveryZone, caloriesTotal, isToday, onClick }: DayCardProps) {
  const zoneColor = recoveryZone === 'GREEN' ? 'var(--success)' : recoveryZone === 'YELLOW' ? '#f0a500' : recoveryZone === 'RED' ? 'var(--accent)' : 'var(--text-disabled)'
  const displayDate = isToday ? 'Today' : formatDate(date)
  const headline = workoutType || 'Rest Day'
  const stats = caloriesTotal > 0 ? `${caloriesTotal} cal` : ''

  return (
    <button className={`day-card${isToday ? ' today' : ''}`} onClick={onClick}>
      <div className="day-card-left">
        <span className="day-card-headline">{headline}</span>
        <span className="day-card-stats">{stats}</span>
      </div>
      <div className="day-card-right">
        {recoveryZone && <span className="day-card-dot" style={{ background: zoneColor }} />}
        <span className="day-card-date">{displayDate}</span>
      </div>
    </button>
  )
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}
