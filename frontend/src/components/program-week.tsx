import { useState } from 'react'
import { ProgramDay } from './program-day'

interface DayData {
  day_of_week: string
  type: string
  planned: string
  note: string
  status: string
}

interface WeekProps {
  week: { number: number; title: string; days: DayData[] }
  today: string
}

export function ProgramWeek({ week }: WeekProps) {
  const isCurrentWeek = week.title.toLowerCase().includes('current') ||
    week.days.some(d => d.status === 'completed')
  const [open, setOpen] = useState(isCurrentWeek)

  const completedDays = week.days.filter(d => d.status === 'completed').length
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
          {week.days.map((day, i) => (
            <ProgramDay key={i} day={day} />
          ))}
        </div>
      )}
    </div>
  )
}
