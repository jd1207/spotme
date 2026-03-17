import { useState } from 'react'

interface DayData {
  day_of_week: string
  type: string
  planned: string
  note: string
  status: string
}

export function ProgramDay({ day }: { day: DayData }) {
  const [expanded, setExpanded] = useState(false)

  const statusIcon = day.status === 'completed' ? '\u2713'
    : day.status === 'today' ? '\u2192' : '\u00b7'
  const statusClass = day.status === 'completed' ? 'completed'
    : day.status === 'today' ? 'today' : 'upcoming'

  // parse planned exercises from comma-separated string
  const exercises = day.planned
    ? day.planned.split(',').map(e => e.trim()).filter(Boolean)
    : []

  return (
    <div
      className={`program-day-card ${statusClass}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="program-day-header">
        <span className={`program-day-status ${statusClass}`}>
          {statusIcon}
        </span>
        <div className="program-day-info">
          <span className="program-day-name">
            {day.day_of_week}: {day.type}
          </span>
          {!expanded && exercises.length > 0 && (
            <span className="program-day-preview">
              {exercises.length} exercise{exercises.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <span className="program-chevron">
          {expanded ? '\u25be' : '\u25b8'}
        </span>
      </div>
      {expanded && (
        <div className="program-day-body">
          {exercises.map((ex, i) => (
            <div key={i} className="program-exercise-item">
              <span className="program-exercise-bullet">{'\u00b7'}</span>
              <span className="program-exercise-text">{ex}</span>
            </div>
          ))}
          {day.note && (
            <div className="program-day-note">{day.note}</div>
          )}
        </div>
      )}
    </div>
  )
}
