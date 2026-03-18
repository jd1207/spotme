import { useState, useEffect } from 'react'
import { api } from '../api'

export function NutritionCard() {
  const [totals, setTotals] = useState<{ calories: number; protein: number } | null>(null)
  const [targets, setTargets] = useState<{ calories: number | null; protein: number | null }>({ calories: null, protein: null })

  useEffect(() => {
    api.getTodayMeals().then(r => setTotals(r.totals)).catch(() => {})
    api.getProfile().then(p => {
      if (p) setTargets({ calories: p.calorie_target, protein: p.protein_target })
    }).catch(() => {})
  }, [])

  if (!totals || totals.calories === 0) return null

  return (
    <div className="nutrition-card">
      <span className="nutrition-label">TODAY'S NUTRITION</span>
      <div className="nutrition-stats">
        <div className="nutrition-stat">
          <span className="nutrition-val">{totals.calories}</span>
          <span className="nutrition-unit">{targets.calories ? `/ ${targets.calories} cal` : 'cal'}</span>
        </div>
        <div className="nutrition-stat">
          <span className="nutrition-val">{Math.round(totals.protein)}</span>
          <span className="nutrition-unit">{targets.protein ? `/ ${targets.protein}g` : 'g protein'}</span>
        </div>
      </div>
      {targets.calories && (
        <div className="nutrition-bar-bg">
          <div className="nutrition-bar-fill" style={{ width: `${Math.min((totals.calories / targets.calories) * 100, 100)}%` }} />
        </div>
      )}
    </div>
  )
}
