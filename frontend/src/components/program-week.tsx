import { useState } from 'react'

interface WeekProps {
  week: { number: number; title: string; items: string[] }
  logged: Record<string, { status: string; duration: number | null; exercises: Array<{ name: string; sets: Array<{ weight: number; reps: number; rpe: number | null }> }> }>
  whoop: Record<string, { recovery: number | null; hrv: number | null }>
  today: string
}

export function ProgramWeek({ week }: WeekProps) {
  const isCurrentWeek = week.title.toLowerCase().includes('current') ||
    week.items.some(item => item.toLowerCase().includes('completed'))
  const [open, setOpen] = useState(isCurrentWeek)

  const hasCompleted = week.items.some(i => i.toLowerCase().includes('completed'))

  return (
    <div className={`program-week${isCurrentWeek ? ' current' : ''}`}>
      <div className="program-week-header" onClick={() => setOpen(!open)}>
        <div className="program-week-left">
          {hasCompleted && <span className="program-week-check">{'\u2713'}</span>}
          <span className="program-week-title">{week.title}</span>
        </div>
        <span className="program-chevron">{open ? '\u25be' : '\u25b8'}</span>
      </div>
      {open && (
        <div className="program-week-body">
          {week.items.map((item, i) => {
            const isCompleted = item.toLowerCase().includes('completed')
            return (
              <div key={i} className={`program-day${isCompleted ? ' completed' : ''}`}>
                <span className="program-day-bullet">{isCompleted ? '\u2713' : '\u00b7'}</span>
                <span className="program-day-text">{item}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
