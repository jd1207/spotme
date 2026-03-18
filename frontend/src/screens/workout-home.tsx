import { useState, useEffect } from 'react'
import { api } from '../api'
import { DayCard } from '../components/day-card'

function todayEastern(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}

interface DayListProps {
  onSelectDay: (date: string) => void
}

export function DayList({ onSelectDay }: DayListProps) {
  const [days, setDays] = useState<Array<{
    date: string
    message_count: number
    workout_type: string | null
    recovery_zone: string | null
    calories_total: number
  }>>([])

  useEffect(() => {
    api.getChatDays().then(r => setDays(r.days)).catch(() => {})
  }, [])

  const today = todayEastern()

  return (
    <div className="day-list-screen">
      <h2 className="day-list-title">Chats</h2>
      {days.length === 0 && (
        <p className="placeholder-text">No chat history yet</p>
      )}
      {days.map(d => (
        <DayCard
          key={d.date}
          date={d.date}
          workoutType={d.workout_type}
          recoveryZone={d.recovery_zone}
          caloriesTotal={d.calories_total}
          isToday={d.date === today}
          onClick={() => onSelectDay(d.date)}
        />
      ))}
    </div>
  )
}
