import { useState, useEffect } from 'react'
import { api } from '../api'
import { WorkoutDetail } from '../components/workout-detail'
import { PrsTab } from '../components/prs-tab'
import { ProgramView } from '../components/program-view'
import { Progress } from './progress'

interface HistoryProps {
  onNavigateWorkout?: () => void
}

type Segment = 'program' | 'log' | 'progress'

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
  const [activeSegment, setActiveSegment] = useState<Segment>('program')
  const [workouts, setWorkouts] = useState<WorkoutEntry[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (activeSegment !== 'log') return
    setLoading(true)
    api.getRecentWorkouts()
      .then(setWorkouts)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [activeSegment])

  const today = new Date().toISOString().split('T')[0]

  return (
    <div className="history-screen">
      <div className="segmented-control">
        {(['program', 'log', 'progress'] as Segment[]).map(seg => (
          <button
            key={seg}
            className={`segment${activeSegment === seg ? ' active' : ''}`}
            onClick={() => setActiveSegment(seg)}
          >
            {seg === 'log' ? 'Log' : seg === 'progress' ? 'Progress' : 'Program'}
          </button>
        ))}
      </div>

      {activeSegment === 'program' && <ProgramView />}

      {activeSegment === 'log' && (
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

      {activeSegment === 'progress' && (
        <>
          <Progress />
          <div className="progress-prs-divider" />
          <PrsTab />
        </>
      )}
    </div>
  )
}
