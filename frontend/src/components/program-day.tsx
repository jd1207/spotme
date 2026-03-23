import { useState } from 'react'

interface SetData {
  weight: number
  reps: number
  rpe: number | null
  set_type: string
  status: string
  target_weight: number | null
  target_reps: number | null
}

interface ExerciseData {
  name: string
  sets: SetData[]
}

interface SummaryData {
  total_sets: number
  top_set: string
  avg_rpe: number | null
}

interface DayData {
  day_of_week: string
  type: string
  planned: string
  note: string
  status: string
  source?: string
  exercises?: ExerciseData[]
  summary?: SummaryData | null
}

function rpeDotColor(rpe: number): string {
  if (rpe <= 7) return 'var(--success)'
  if (rpe <= 8) return 'var(--info)'
  if (rpe <= 9) return '#f0a500'
  return 'var(--accent)'
}

function avgRpeLabel(avgRpe: number | null): string {
  if (avgRpe === null) return ''
  if (avgRpe <= 7) return 'Easy'
  if (avgRpe <= 8) return 'Solid'
  if (avgRpe <= 9) return 'Tough'
  return 'Max'
}

function LoggedBody({ exercises, summary }: { exercises: ExerciseData[]; summary: SummaryData | null | undefined }) {
  return (
    <div>
      {summary && (
        <div className="program-day-summary">
          {summary.total_sets} sets
          {summary.top_set ? ` · Top: ${summary.top_set}` : ''}
          {summary.avg_rpe !== null ? ` · ${avgRpeLabel(summary.avg_rpe)}` : ''}
        </div>
      )}
      {exercises.map((ex, ei) => (
        <div key={ei} className="program-exercise-group">
          <div className="program-exercise-group-name">{ex.name}</div>
          <div className="program-set-list">
            {ex.sets.map((s, si) => {
              const isWarmup = s.set_type === 'warmup'
              const rowClass = `program-set-row${isWarmup ? ' warmup' : ' working'}`
              return (
                <div key={si} className={rowClass}>
                  <span className="program-set-weight">{s.weight} x {s.reps}</span>
                  {isWarmup && (
                    <span className="program-set-type-label">warm-up</span>
                  )}
                  {!isWarmup && s.rpe !== null && (
                    <span
                      className="program-set-rpe-dot"
                      style={{ backgroundColor: rpeDotColor(s.rpe) }}
                    />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

function splitExercises(text: string): string[] {
  // split on commas, but not inside parentheses
  const parts: string[] = []
  let depth = 0
  let current = ''
  for (const ch of text) {
    if (ch === '(') depth++
    else if (ch === ')') depth = Math.max(0, depth - 1)
    if (ch === ',' && depth === 0) {
      const trimmed = current.trim()
      if (trimmed) parts.push(trimmed)
      current = ''
    } else {
      current += ch
    }
  }
  const trimmed = current.trim()
  if (trimmed) parts.push(trimmed)
  return parts
}

function PlannedBody({ day }: { day: DayData }) {
  const exercises = day.planned ? splitExercises(day.planned) : []
  return (
    <div>
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
  )
}

export function ProgramDay({ day }: { day: DayData }) {
  const [expanded, setExpanded] = useState(false)

  const statusIcon = day.status === 'completed' ? '\u2713'
    : day.status === 'today' ? '\u2192' : '\u00b7'
  const statusClass = day.status === 'completed' ? 'completed'
    : day.status === 'today' ? 'today' : 'upcoming'

  const plannedExercises = day.planned ? splitExercises(day.planned) : []

  const hasLoggedData = day.source === 'logged' && day.exercises && day.exercises.length > 0

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
          {!expanded && plannedExercises.length > 0 && (
            <span className="program-day-preview">
              {plannedExercises.length} exercise{plannedExercises.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <span className="program-chevron">
          {expanded ? '\u25be' : '\u25b8'}
        </span>
      </div>
      {expanded && (
        <div className="program-day-body">
          {hasLoggedData
            ? <LoggedBody exercises={day.exercises!} summary={day.summary} />
            : <PlannedBody day={day} />
          }
        </div>
      )}
    </div>
  )
}
