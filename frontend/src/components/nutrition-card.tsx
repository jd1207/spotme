import { useState, useEffect } from 'react'
import { api } from '../api'

export function NutritionCard() {
  const [totals, setTotals] = useState<{ calories: number; protein: number } | null>(null)

  useEffect(() => {
    api.getTodayMeals()
      .then(r => setTotals(r.totals))
      .catch(() => {})
  }, [])

  if (!totals || totals.calories === 0) return null

  return (
    <div className="nutrition-card">
      <span className="nutrition-label">TODAY'S NUTRITION</span>
      <div className="nutrition-stats">
        <div className="nutrition-stat">
          <span className="nutrition-val">{totals.calories}</span>
          <span className="nutrition-unit">cal</span>
        </div>
        <div className="nutrition-stat">
          <span className="nutrition-val">{Math.round(totals.protein)}</span>
          <span className="nutrition-unit">g protein</span>
        </div>
      </div>
    </div>
  )
}
