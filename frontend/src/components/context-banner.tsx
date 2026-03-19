import { useState, useEffect } from 'react'
import { api } from '../api'

interface ContextBannerProps {
  date: string
}

export function ContextBanner({ date }: ContextBannerProps) {
  const [recovery, setRecovery] = useState<{ score: number; zone: string } | null>(null)
  const [workoutType, setWorkoutType] = useState<string | null>(null)
  const [nutrition, setNutrition] = useState<{ current: number; target: number | null } | null>(null)
  const [whoopStale, setWhoopStale] = useState(false)

  useEffect(() => {
    api.getChatDays().then(r => {
      const day = r.days.find((d: any) => d.date === date)
      if (day) {
        if (day.recovery_score && day.recovery_zone) setRecovery({ score: day.recovery_score, zone: day.recovery_zone })
        if (day.workout_type) setWorkoutType(day.workout_type)
        setNutrition({ current: day.calories_total, target: null })
      }
    }).catch(() => {})
    api.getProfile().then(p => {
      if (p?.calorie_target) {
        setNutrition(prev => prev ? { ...prev, target: p.calorie_target } : null)
      }
    }).catch(() => {})

    api.whoopLatest().then(r => {
      if (r.data && r.data.date !== new Date().toISOString().slice(0, 10)) {
        setWhoopStale(true)
      } else {
        setWhoopStale(false)
      }
    }).catch(() => {})
  }, [date])

  const hasData = recovery || workoutType || (nutrition && nutrition.current > 0)
  if (!hasData) return null

  const zoneColor = recovery?.zone === 'GREEN' ? 'var(--success)' : recovery?.zone === 'YELLOW' ? '#f0a500' : 'var(--accent)'

  return (
    <div className="context-banner">
      {recovery && (
        <div className="context-row">
          <span className="context-dot" style={{ background: zoneColor }} />
          <span className="context-text">
            {recovery.zone} {recovery.score}% Recovery
            {whoopStale && ' (yesterday)'}
          </span>
        </div>
      )}
      {workoutType && <span className="context-workout">{workoutType}</span>}
      {nutrition && nutrition.current > 0 && (
        <span className="context-nutrition">
          {nutrition.current}{nutrition.target ? ` / ${nutrition.target}` : ''} cal
        </span>
      )}
    </div>
  )
}
