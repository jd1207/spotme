import { useState, useEffect } from 'react'
import { api } from '../api'
import { MiniChart } from '../components/mini-chart'
import { MealCard } from '../components/meal-card'
import type { TrendPoint } from '../types'

interface MealItem {
  id: number
  description: string
  calories: number | null
  protein: number | null
  carbs: number | null
  fat: number | null
  meal_type: string | null
  items: string[] | null
  created_at: string | null
}

interface Totals { calories: number; protein: number; carbs: number; fat: number }
interface Targets { calories: number | null; protein: number | null }

interface DayAggregate {
  date: string
  calories: number
  protein: number
}

interface PrevDayCardProps {
  day: DayAggregate
}

function ProgressBar({ current, target, color }: { current: number; target: number; color: string }) {
  const pct = Math.min((current / target) * 100, 100)
  return (
    <div className="diet-bar-bg">
      <div className="diet-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

function PrevDayCard({ day }: PrevDayCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [meals, setMeals] = useState<MealItem[]>([])
  const [loading, setLoading] = useState(false)

  const label = (() => {
    const today = new Date()
    const d = new Date(day.date + 'T00:00:00')
    const diff = Math.round((today.setHours(0,0,0,0), today.valueOf() - d.valueOf()) / 86400000)
    if (diff === 1) return 'Yesterday'
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  })()

  const toggle = async () => {
    if (!expanded && meals.length === 0) {
      setLoading(true)
      try {
        const r = await api.getMealsDay(day.date)
        setMeals(r.meals)
      } catch { /* ignore */ }
      setLoading(false)
    }
    setExpanded(e => !e)
  }

  return (
    <div className="diet-prev-card">
      <button className="diet-prev-header" onClick={toggle}>
        <span className="diet-prev-label">{label}</span>
        <span className="diet-prev-summary">{day.calories} cal &middot; {Math.round(day.protein)}g P</span>
        <span className="diet-prev-chevron">{expanded ? '▾' : '▸'}</span>
      </button>
      {expanded && (
        <div className="diet-prev-meals">
          {loading && <p className="diet-empty">Loading…</p>}
          {!loading && meals.length === 0 && <p className="diet-empty">No meals recorded.</p>}
          {meals.map(m => (
            <div key={m.id} className="diet-meal-card diet-meal-card--readonly">
              {m.meal_type && <div className="diet-meal-header">{m.meal_type}</div>}
              <div className="diet-meal-body">
                {m.items && m.items.length > 0 ? (
                  <ul className="diet-meal-items">{m.items.map((it, i) => <li key={i}>{it}</li>)}</ul>
                ) : (
                  <span className="diet-meal-desc">{m.description}</span>
                )}
                <span className="diet-meal-macros">{m.calories ?? 0} cal &middot; {Math.round(m.protein ?? 0)}g protein</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function Diet() {
  const [meals, setMeals] = useState<MealItem[]>([])
  const [totals, setTotals] = useState<Totals | null>(null)
  const [weekData, setWeekData] = useState<TrendPoint[]>([])
  const [prevDays, setPrevDays] = useState<DayAggregate[]>([])
  const [targets, setTargets] = useState<Targets>({ calories: null, protein: null })

  const loadToday = () => api.getTodayMeals().then(r => { setMeals(r.meals); setTotals(r.totals) }).catch(() => {})

  useEffect(() => {
    loadToday()
    api.getWeekMeals().then(r => {
      const today = new Date().toISOString().slice(0, 10)
      const trend = r.days.map(d => ({ date: d.date, calories: d.calories, protein: d.protein }))
      setWeekData(trend)
      setPrevDays(r.days.filter(d => d.date !== today).reverse())
    }).catch(() => {})
    api.getProfile().then(p => { if (p) setTargets({ calories: p.calorie_target, protein: p.protein_target }) }).catch(() => {})
  }, [])

  const handleDelete = async (id: number) => { await api.deleteMeal(id); loadToday() }
  const handleFix = async (id: number) => { await api.deleteMeal(id); loadToday() }

  const cal = totals?.calories ?? 0
  const pro = totals?.protein ?? 0
  const calRemaining = targets.calories ? Math.max(0, targets.calories - cal) : null
  const proRemaining = targets.protein ? Math.max(0, targets.protein - pro) : null

  return (
    <div className="diet-screen">
      <h2 className="diet-title">Diet</h2>

      <div className="diet-macro-progress">
        <div className="diet-progress-row">
          <span className="diet-progress-label">Calories</span>
          {targets.calories ? (
            <><ProgressBar current={cal} target={targets.calories} color="var(--accent)" />
            <span className="diet-progress-text">{cal} / {targets.calories}</span></>
          ) : <span className="diet-progress-text">{cal} cal</span>}
        </div>
        <div className="diet-progress-row">
          <span className="diet-progress-label">Protein</span>
          {targets.protein ? (
            <><ProgressBar current={pro} target={targets.protein} color="var(--info)" />
            <span className="diet-progress-text">{Math.round(pro)}g / {targets.protein}g</span></>
          ) : <span className="diet-progress-text">{Math.round(pro)}g</span>}
        </div>
        {totals && (totals.carbs > 0 || totals.fat > 0) && (
          <div className="diet-breakdown">
            <span className="diet-breakdown-item">{Math.round(totals.carbs)}g carbs</span>
            <span className="diet-breakdown-item">{Math.round(totals.fat)}g fat</span>
          </div>
        )}
        {(calRemaining !== null || proRemaining !== null) && (
          <div className="diet-remaining-row">
            <span className="diet-remaining">
              {calRemaining !== null && `${calRemaining} cal`}
              {calRemaining !== null && proRemaining !== null && ' · '}
              {proRemaining !== null && `${Math.round(proRemaining)}g protein`}
              {(calRemaining !== null || proRemaining !== null) && ' to go'}
            </span>
            <button className="diet-cta" onClick={() => console.log('get meal ideas')}>Get meal ideas →</button>
          </div>
        )}
        {!targets.calories && !targets.protein && (
          <p className="diet-targets-hint">Tell Claude your daily targets to see progress bars</p>
        )}
      </div>

      {weekData.length > 1 && (
        <div className="diet-trends">
          <h3 className="diet-section-title">7-Day Trends</h3>
          <MiniChart data={weekData} valueKey="calories" label="Calories" unit=" cal" color="var(--accent)" />
          <MiniChart data={weekData} valueKey="protein" label="Protein" unit="g" color="var(--info)" />
        </div>
      )}

      <div className="diet-meals">
        <h3 className="diet-section-title">Today's Meals</h3>
        {meals.length === 0 && <p className="diet-empty">No meals logged yet. Chat with Claude to log food.</p>}
        {meals.map(m => <MealCard key={m.id} meal={m} onDelete={handleDelete} onFix={handleFix} />)}
      </div>

      {prevDays.length > 0 && (
        <div className="diet-prev-days">
          <h3 className="diet-section-title">Previous Days</h3>
          {prevDays.map(d => <PrevDayCard key={d.date} day={d} />)}
        </div>
      )}
    </div>
  )
}
