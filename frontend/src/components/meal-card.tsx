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

interface MealCardProps {
  meal: MealItem
  onDelete: (id: number) => void
  onFix: (id: number) => void
}

function formatTime(created_at: string | null): string {
  if (!created_at) return ''
  try {
    const d = new Date(created_at)
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
  } catch {
    return ''
  }
}

export function MealCard({ meal, onDelete, onFix }: MealCardProps) {
  const time = formatTime(meal.created_at)
  const header = [meal.meal_type, time].filter(Boolean).join(' · ')

  return (
    <div className="diet-meal-card">
      {header && <div className="diet-meal-header">{header}</div>}
      <div className="diet-meal-body">
        {meal.items && meal.items.length > 0 ? (
          <ul className="diet-meal-items">
            {meal.items.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        ) : (
          <span className="diet-meal-desc">{meal.description}</span>
        )}
        <span className="diet-meal-macros">
          {meal.calories ?? 0} cal &middot; {Math.round(meal.protein ?? 0)}g protein
        </span>
      </div>
      <div className="diet-meal-actions">
        <button className="diet-meal-fix" onClick={() => onFix(meal.id)}>Fix</button>
        <button className="diet-meal-delete" onClick={() => onDelete(meal.id)}>&times;</button>
      </div>
    </div>
  )
}
