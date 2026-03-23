import { useState, useEffect } from 'react'
import { api } from '../api'
import { ProgramWeek } from './program-week'

interface DayData {
  day_of_week: string
  type: string
  planned: string
  note: string
  status: string
}

interface WeekData {
  number: number
  title: string
  days: DayData[]
  start_date?: string | null
}

interface ProgressionPoint { week: number; weight: number; label: string }

interface ProgramData {
  has_program: boolean
  weeks: WeekData[]
  progression: ProgressionPoint[]
  stats: { total_workouts: number; completed_workouts: number; today: string }
}

export function ProgramView() {
  const [data, setData] = useState<ProgramData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getProgram()
      .then(r => setData(r as ProgramData))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="placeholder-text">Loading program...</p>
  if (!data?.has_program) return (
    <div className="placeholder-view">
      <p className="placeholder-text">No program loaded yet.</p>
      <p className="placeholder-text">Chat with Claude to set up your training plan.</p>
    </div>
  )

  const maxWeight = Math.max(...(data.progression.map(p => p.weight)), 1)

  return (
    <div className="program-view">
      <div className="program-stats">
        <span>{data.stats.completed_workouts} workouts done</span>
      </div>

      {data.progression.length > 0 && (
        <div className="program-progression">
          <span className="program-progression-label">Bench Peak Progression</span>
          <div className="program-progression-bars">
            {data.progression.map(p => (
              <div key={p.week} className="program-progression-col">
                <span className="program-progression-weight">{p.weight}</span>
                <div
                  className="program-progression-bar"
                  style={{ height: `${(p.weight / maxWeight) * 100}%` }}
                />
                <span className="program-progression-week">{p.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.weeks.map(w => (
        <ProgramWeek key={w.number} week={w} today={data.stats.today} />
      ))}
    </div>
  )
}
