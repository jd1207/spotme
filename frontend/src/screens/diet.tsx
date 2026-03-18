import { useState, useEffect } from 'react'
import { api } from '../api'
import { MiniChart } from '../components/mini-chart'
import type { TrendPoint } from '../types'

interface MealItem {
  id: number
  description: string
  calories: number | null
  protein: number | null
  carbs: number | null
  fat: number | null
  meal_type: string | null
}

interface Totals {
  calories: number
  protein: number
  carbs: number
  fat: number
}

interface Targets {
  calories: number | null
  protein: number | null
}

function ProgressBar({ current, target, color }: { current: number; target: number; color: string }) {
  const pct = Math.min((current / target) * 100, 100)
  return (
    <div className="diet-bar-bg">
      <div className="diet-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

export function Diet() {
  const [meals, setMeals] = useState<MealItem[]>([])
  const [totals, setTotals] = useState<Totals | null>(null)
  const [weekData, setWeekData] = useState<TrendPoint[]>([])
  const [targets, setTargets] = useState<Targets>({ calories: null, protein: null })

  useEffect(() => {
    api.getTodayMeals().then(r => {
      setMeals(r.meals)
      setTotals(r.totals)
    }).catch(() => {})
    api.getWeekMeals().then(r => {
      setWeekData(r.days.map(d => ({ date: d.date, calories: d.calories, protein: d.protein })))
    }).catch(() => {})
    api.getProfile().then(p => {
      if (p) setTargets({ calories: p.calorie_target, protein: p.protein_target })
    }).catch(() => {})
  }, [])

  const handleDelete = async (id: number) => {
    await api.deleteMeal(id)
    const r = await api.getTodayMeals()
    setMeals(r.meals)
    setTotals(r.totals)
  }

  const cal = totals?.calories ?? 0
  const pro = totals?.protein ?? 0

  return (
    <div className="diet-screen">
      <h2 className="diet-title">Diet</h2>

      <div className="diet-macro-progress">
        <div className="diet-progress-row">
          <span className="diet-progress-label">Calories</span>
          {targets.calories ? (
            <>
              <ProgressBar current={cal} target={targets.calories} color="var(--accent)" />
              <span className="diet-progress-text">{cal} / {targets.calories}</span>
            </>
          ) : (
            <span className="diet-progress-text">{cal} cal</span>
          )}
        </div>
        <div className="diet-progress-row">
          <span className="diet-progress-label">Protein</span>
          {targets.protein ? (
            <>
              <ProgressBar current={pro} target={targets.protein} color="var(--info)" />
              <span className="diet-progress-text">{Math.round(pro)}g / {targets.protein}g</span>
            </>
          ) : (
            <span className="diet-progress-text">{Math.round(pro)}g</span>
          )}
        </div>
        {totals && (totals.carbs > 0 || totals.fat > 0) && (
          <div className="diet-breakdown">
            <span className="diet-breakdown-item">{Math.round(totals.carbs)}g carbs</span>
            <span className="diet-breakdown-item">{Math.round(totals.fat)}g fat</span>
          </div>
        )}
        {!targets.calories && !targets.protein && (
          <p className="diet-targets-hint">Tell Claude your daily targets to see progress bars</p>
        )}
      </div>

      <div className="diet-meals">
        <h3 className="diet-section-title">Today's Meals</h3>
        {meals.length === 0 && (
          <p className="diet-empty">No meals logged yet. Chat with Claude to log food.</p>
        )}
        {meals.map(m => (
          <div key={m.id} className="diet-meal-card">
            <div className="diet-meal-info">
              <span className="diet-meal-desc">{m.description}</span>
              <span className="diet-meal-macros">
                {m.calories ?? 0} cal &middot; {Math.round(m.protein ?? 0)}g protein
              </span>
            </div>
            <button className="diet-meal-delete" onClick={() => handleDelete(m.id)}>&times;</button>
          </div>
        ))}
      </div>

      {weekData.length > 1 && (
        <div className="diet-trends">
          <h3 className="diet-section-title">7-Day Trends</h3>
          <MiniChart data={weekData} valueKey="calories" label="Calories" unit=" cal" color="var(--accent)" />
          <MiniChart data={weekData} valueKey="protein" label="Protein" unit="g" color="var(--info)" />
        </div>
      )}
    </div>
  )
}
