import { useState, useEffect } from 'react'
import { api } from '../api'
import { RecoveryBanner } from '../components/recovery-banner'
import { NutritionCard } from '../components/nutrition-card'
import type { WhoopStats } from '../types'

interface WorkoutHomeProps {
  onStartWorkout: () => void
  onStartChat: () => void
  onViewPast: (id: number) => void
}

export function WorkoutHome({ onStartWorkout, onStartChat, onViewPast }: WorkoutHomeProps) {
  const [recentWorkouts, setRecentWorkouts] = useState<Array<{ id: number; date: string; type: string; status: string }>>([])
  const [nextWorkout, setNextWorkout] = useState<string | null>(null)
  const [whoop, setWhoop] = useState<WhoopStats | null>(null)

  useEffect(() => {
    api.getRecentWorkouts().then(setRecentWorkouts).catch(() => {})
    api.getNextWorkout().then(r => setNextWorkout(r.summary)).catch(() => {})
    api.whoopLatest().then(r => setWhoop(r.data)).catch(() => {})
  }, [])

  return (
    <div className="workout-home">
      <div className="workout-home-header">
        <h2>Ready to train?</h2>
        <p>Start a workout or chat with Claude about your program.</p>
      </div>
      {whoop && (
        <RecoveryBanner
          recovery={whoop.recovery_score}
          hrv={whoop.hrv}
          sleep={whoop.sleep_score}
          strain={whoop.strain}
        />
      )}
      <NutritionCard />
      {nextWorkout && !nextWorkout.startsWith('No program') && (
        <div className="workout-plan-preview">
          <span className="workout-plan-label">TODAY'S PLAN</span>
          <p className="workout-plan-text">{nextWorkout}</p>
        </div>
      )}
      <div className="home-actions">
        <button className="start-workout-btn" onClick={onStartWorkout}>Start Workout</button>
        <button className="general-chat-btn" onClick={onStartChat}>Chat with Claude</button>
      </div>

      {recentWorkouts.length > 0 && (
        <div className="recent-workouts">
          <h3 className="recent-title">Recent Sessions</h3>
          {recentWorkouts.map(w => (
            <button key={w.id} className={`recent-workout-card ${w.status}`} onClick={() => onViewPast(w.id)}>
              <span className="recent-date">{w.date}</span>
              <span className="recent-type">{w.type}</span>
              <span className="recent-status">{w.status === 'active' ? 'In Progress' : 'Completed'}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
