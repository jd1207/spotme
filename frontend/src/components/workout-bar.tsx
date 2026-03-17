interface ExerciseEntry {
  name: string
  status: 'done' | 'current' | 'upcoming'
  summary?: string
  setProgress?: string
}

interface WorkoutBarProps {
  exerciseName: string
  setProgress: string
  restSeconds: number
  restActive: boolean
  expanded: boolean
  onToggle: () => void
  programName?: string
  whoopRecovery?: number
  whoopHrv?: number
  whoopRhr?: number
  exercises?: ExerciseEntry[]
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function StatusIcon({ status }: { status: ExerciseEntry['status'] }) {
  if (status === 'done') {
    return <span className="exercise-status done">{'\u2713'}</span>
  }
  if (status === 'current') {
    return <span className="exercise-status current">{'\u25CF'}</span>
  }
  return <span className="exercise-status upcoming">{'\u2014'}</span>
}

export function WorkoutBar({
  exerciseName,
  setProgress,
  restSeconds,
  restActive,
  expanded,
  onToggle,
  programName,
  whoopRecovery,
  whoopHrv,
  whoopRhr,
  exercises,
}: WorkoutBarProps) {
  return (
    <div className={`workout-bar${expanded ? ' expanded' : ''}`}>
      <div className="workout-bar-header" onClick={onToggle}>
        <span className="workout-bar-exercise">
          {expanded && programName ? programName : exerciseName}
        </span>
        <span className="workout-bar-sets">{setProgress}</span>
        <span className={`workout-bar-timer${restActive ? ' active' : ''}`}>
          {formatTime(restSeconds)}
        </span>
        <span className="workout-bar-arrow">{expanded ? '\u25B2' : '\u25BC'}</span>
      </div>

      {expanded && (
        <div className="workout-bar-details">
          {(whoopRecovery != null || whoopHrv != null || whoopRhr != null) && (
            <div className="workout-bar-whoop">
              {whoopRecovery != null && (
                <span className="whoop-stat">
                  <span className="whoop-dot recovery" />
                  {whoopRecovery}% Recovery
                </span>
              )}
              {whoopHrv != null && (
                <span className="whoop-stat">
                  <span className="whoop-dot hrv" />
                  {whoopHrv} HRV
                </span>
              )}
              {whoopRhr != null && (
                <span className="whoop-stat">
                  <span className="whoop-dot rhr" />
                  {whoopRhr} RHR
                </span>
              )}
            </div>
          )}

          {exercises && exercises.length > 0 && (
            <ul className="workout-bar-exercises">
              {exercises.map((ex) => (
                <li key={ex.name} className={`exercise-item ${ex.status}`}>
                  <StatusIcon status={ex.status} />
                  <span className="exercise-name">{ex.name}</span>
                  {ex.status === 'done' && ex.summary && (
                    <span className="exercise-summary">{ex.summary}</span>
                  )}
                  {ex.status === 'current' && ex.setProgress && (
                    <span className="exercise-set-progress">{ex.setProgress}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
