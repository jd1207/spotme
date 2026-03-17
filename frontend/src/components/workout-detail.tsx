import { useState } from 'react'

interface WorkoutSet {
  weight: number
  reps: number
  rpe: number | null
}

interface WorkoutExercise {
  name: string
  sets: WorkoutSet[]
}

interface WorkoutDetailProps {
  date: string
  type: string
  status: string
  duration: number | null
  exercises: WorkoutExercise[]
  recovery: number | null
  onView?: () => void
}

export function WorkoutDetail({ date, type, status, duration, exercises, recovery, onView }: WorkoutDetailProps) {
  const [expanded, setExpanded] = useState(false)

  const recoveryColor = recovery == null ? 'var(--text-disabled)'
    : recovery >= 67 ? 'var(--success)'
    : recovery >= 34 ? '#f5a623' : '#e57373'

  const formatted = new Date(date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  })

  return (
    <div className="workout-detail-card" onClick={() => setExpanded(!expanded)}>
      <div className="workout-detail-header">
        <div className="workout-detail-left">
          <span className="workout-detail-date">{formatted}</span>
          <span className="workout-detail-type">{type}{duration ? ` · ${duration}m` : ''}</span>
        </div>
        <div className="workout-detail-right">
          {recovery != null && (
            <span className="workout-detail-recovery" style={{ color: recoveryColor }}>
              {Math.round(recovery)}%
            </span>
          )}
          {status === 'completed' && <span className="workout-detail-check">&#10003;</span>}
          {status === 'active' && onView && (
            <button className="workout-detail-go" onClick={e => { e.stopPropagation(); onView() }}>GO</button>
          )}
        </div>
      </div>
      {!expanded && exercises.length > 0 && (
        <span className="workout-detail-summary">
          {exercises.map(e => e.name).join(', ')}
        </span>
      )}
      {expanded && exercises.length > 0 && (
        <div className="workout-detail-exercises">
          {exercises.map((ex, i) => (
            <div key={i} className="workout-detail-exercise">
              <span className="workout-detail-exname">{ex.name}</span>
              <div className="workout-detail-sets">
                {ex.sets.map((s, j) => (
                  <span key={j} className="workout-detail-set">
                    {s.weight}x{s.reps}{s.rpe ? ` @${s.rpe}` : ''}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
