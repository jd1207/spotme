import { useState, useEffect } from 'react'
import { api } from '../api'
import { ProgramDay } from './program-day'

interface DayData {
  day_of_week: string
  type: string
  planned: string
  note: string
  status: string
  source?: string
  exercises?: Array<{ name: string; sets: Array<{ weight: number; reps: number; rpe: number | null; set_type: string; status: string; target_weight: number | null; target_reps: number | null }> }>
  summary?: { total_sets: number; top_set: string; avg_rpe: number | null } | null
}

interface WeekProps {
  week: { number: number; title: string; days: DayData[]; start_date?: string | null }
  today: string
}

function isWeekCurrent(week: WeekProps['week'], today: string): boolean {
  if (week.title.toLowerCase().includes('current')) return true
  if (week.start_date) {
    const start = new Date(week.start_date + 'T00:00:00')
    const end = new Date(start)
    end.setDate(end.getDate() + 7)
    const t = new Date(today + 'T00:00:00')
    return t >= start && t < end
  }
  return false
}

export function ProgramWeek({ week, today }: WeekProps) {
  const isCurrentWeek = isWeekCurrent(week, today)
  const [open, setOpen] = useState(isCurrentWeek)
  const [enrichedDays, setEnrichedDays] = useState<DayData[] | null>(null)

  useEffect(() => {
    if (!open) return
    api.getProgramWeek(week.number)
      .then(r => setEnrichedDays(r.days))
      .catch(() => {})
  }, [open, week.number])

  const displayDays = enrichedDays ?? week.days
  const completedDays = displayDays.filter(d => d.status === 'completed').length
  const totalDays = week.days.length

  return (
    <div className={`program-week${isCurrentWeek ? ' current' : ''}`}>
      <div className="program-week-header" onClick={() => setOpen(!open)}>
        <div className="program-week-left">
          <span className="program-week-title">{week.title}</span>
          <span className="program-week-progress">
            {completedDays}/{totalDays} done
          </span>
        </div>
        <span className="program-chevron">{open ? '\u25be' : '\u25b8'}</span>
      </div>
      {open && (
        <div className="program-week-body">
          {displayDays.map((day, i) => (
            <ProgramDay key={i} day={day} />
          ))}
        </div>
      )}
    </div>
  )
}
