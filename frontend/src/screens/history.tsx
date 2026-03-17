import { useState, useEffect } from 'react'
import { api } from '../api'
import { WorkoutDetail } from '../components/workout-detail'
import { PrsTab } from '../components/prs-tab'

interface HistoryProps {
  onNavigateWorkout?: () => void
}

type Segment = 'workouts' | 'prs'

interface WorkoutExercise {
  name: string
  sets: Array<{ weight: number; reps: number; rpe: number | null }>
}

interface WorkoutEntry {
  id: number
  date: string
  type: string
  status: string
  duration: number | null
  exercises: WorkoutExercise[]
  recovery: number | null
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
            <WorkoutDetail
              key={w.id}
              date={w.date}
              type={w.type}
              status={w.status}
              duration={w.duration}
              exercises={w.exercises}
              recovery={w.recovery}
              onView={w.status === 'active' && w.date === today ? onNavigateWorkout : undefined}
            />
          ))}
        </div>
      )}

      {activeSegment === 'prs' && <PrsTab />}
    </div>
  )
}
