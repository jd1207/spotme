import { useState, useEffect } from 'react'
import { api } from '../api'

interface PR {
  exercise: string
  weight: number
  reps: number
  e1rm: number
  date: string
}

export function PrsTab() {
  const [prs, setPrs] = useState<PR[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getPrs()
      .then(r => setPrs(r.prs))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="history-loading">Loading PRs...</div>
  if (prs.length === 0) return <div className="history-empty">No PRs yet. Complete some workouts!</div>

  return (
    <div className="prs-list">
      {prs.map((pr, i) => (
        <div key={i} className="pr-card">
          <div className="pr-header">
            <span className="pr-exercise">{pr.exercise}</span>
            <span className="pr-e1rm">{pr.e1rm} lbs</span>
          </div>
          <div className="pr-detail">
            <span>Best set: {pr.weight}x{pr.reps}</span>
            <span>{new Date(pr.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
