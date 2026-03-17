import { useState, useEffect } from 'react'
import { api } from '../api'

interface HistoryProps {
  onNavigateWorkout?: () => void
}

type Segment = 'workouts' | 'prs'

interface WorkoutEntry {
  id: number
  date: string
  type: string
  status: string
  duration: number | null
}

export function History({ onNavigateWorkout }: HistoryProps) {
  const [activeSegment, setActiveSegment] = useState<Segment>('workouts')
  const [workouts, setWorkouts] = useState<WorkoutEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getRecentWorkouts()
      .then(setWorkouts)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const today = new Date().toISOString().split('T')[0]

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + 'T12:00:00')
    const day = d.toLocaleDateString('en-US', { weekday: 'short' })
    const month = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    return `${day}, ${month}`
  }

  return (
    <div className="history-screen">
      <div className="segmented-control">
        {(['workouts', 'prs'] as Segment[]).map(seg => (
          <button
            key={seg}
            className={`segment${activeSegment === seg ? ' active' : ''}`}
            onClick={() => setActiveSegment(seg)}
          >
            {seg === 'prs' ? 'PRs' : 'Workouts'}
          </button>
        ))}
      </div>

      {activeSegment === 'workouts' && (
        <div className="workouts-list">
          {loading && <p className="placeholder-text">Loading...</p>}
          {!loading && workouts.length === 0 && (
            <div className="placeholder-view">
              <p className="placeholder-text">No workouts yet. Start your first session!</p>
            </div>
          )}
          {workouts.map(w => (
            <div key={w.id} className={`session-card ${w.status}`}>
              <div className="session-card-content">
                <div className="session-card-top">
                  <span className="session-day">{formatDate(w.date)}</span>
                  <span className="session-type">{w.type}</span>
                </div>
                {w.duration && (
                  <p className="session-exercises">{w.duration} min</p>
                )}
              </div>
              {w.status === 'active' && w.date === today && onNavigateWorkout && (
                <button className="session-go-btn" onClick={onNavigateWorkout}>GO</button>
              )}
              {w.status === 'completed' && (
                <span className="session-check">&#10003;</span>
              )}
            </div>
          ))}
        </div>
      )}

      {activeSegment === 'prs' && (
        <div className="placeholder-view">
          <p className="placeholder-text">Coming soon</p>
        </div>
      )}
    </div>
  )
}
