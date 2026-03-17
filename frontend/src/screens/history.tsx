import { useState } from 'react'
import type { WeekData } from '../types'

interface HistoryProps {
  onNavigateWorkout?: () => void
}

type Segment = 'program' | 'workouts' | 'prs'

const MOCK_WEEKS: WeekData[] = [
  {
    number: 1, label: 'Week 1', completed: 4, total: 4,
    sessions: [
      { day: 'Mon', type: 'Upper', status: 'completed', exercises: 'Bench 185x5, OHP 115x8, Rows 155x8', recovery: 78, strain: 14.2, duration: 62 },
      { day: 'Wed', type: 'Lower', status: 'completed', exercises: 'Squat 275x5, RDL 225x8, Leg Press 360x10', recovery: 65, strain: 16.1, duration: 70 },
      { day: 'Fri', type: 'Upper', status: 'completed', exercises: 'Bench 190x5, OHP 120x7, Rows 160x8', recovery: 82, strain: 13.8, duration: 58 },
      { day: 'Sat', type: 'Lower', status: 'completed', exercises: 'Squat 280x5, RDL 230x8, Leg Curl 3x12', recovery: 71, strain: 15.5, duration: 65 },
    ],
  },
  {
    number: 2, label: 'Week 2', completed: 4, total: 4,
    sessions: [
      { day: 'Mon', type: 'Upper', status: 'completed', exercises: 'Bench 195x5, OHP 120x8, Rows 160x8', recovery: 80, strain: 14.5, duration: 60 },
      { day: 'Wed', type: 'Lower', status: 'completed', exercises: 'Squat 285x5, RDL 235x8, Leg Press 370x10', recovery: 68, strain: 16.3, duration: 68 },
      { day: 'Fri', type: 'Upper', status: 'completed', exercises: 'Bench 200x4, OHP 125x7, Rows 165x8', recovery: 75, strain: 14.1, duration: 59 },
      { day: 'Sat', type: 'Lower', status: 'completed', exercises: 'Squat 290x4, RDL 235x8, Leg Curl 3x12', recovery: 72, strain: 15.8, duration: 66 },
    ],
  },
  {
    number: 3, label: 'Week 3', completed: 4, total: 4,
    sessions: [
      { day: 'Mon', type: 'Upper', status: 'completed', exercises: 'Bench 205x4, OHP 125x8, Rows 165x8', recovery: 84, strain: 14.8, duration: 61 },
      { day: 'Wed', type: 'Lower', status: 'completed', exercises: 'Squat 295x4, RDL 240x8, Leg Press 380x10', recovery: 70, strain: 16.5, duration: 72 },
      { day: 'Fri', type: 'Upper', status: 'completed', exercises: 'Bench 210x3, OHP 130x6, Rows 170x8', recovery: 77, strain: 14.3, duration: 60 },
      { day: 'Sat', type: 'Lower', status: 'completed', exercises: 'Squat 300x3, RDL 245x7, Leg Curl 3x12', recovery: 69, strain: 16.0, duration: 67 },
    ],
  },
  {
    number: 4, label: 'Week 4 (Deload)', completed: 4, total: 4,
    sessions: [
      { day: 'Mon', type: 'Upper', status: 'completed', exercises: 'Bench 175x8, OHP 105x10, Rows 135x10', recovery: 88, strain: 10.2, duration: 45 },
      { day: 'Wed', type: 'Lower', status: 'completed', exercises: 'Squat 225x8, RDL 185x10, Leg Press 300x12', recovery: 90, strain: 11.0, duration: 48 },
      { day: 'Fri', type: 'Upper', status: 'completed', exercises: 'Bench 180x8, OHP 110x10, Rows 140x10', recovery: 92, strain: 10.5, duration: 44 },
      { day: 'Sat', type: 'Lower', status: 'completed', exercises: 'Squat 230x8, RDL 190x10, Leg Curl 3x15', recovery: 85, strain: 11.3, duration: 46 },
    ],
  },
  {
    number: 5, label: 'Week 5', completed: 4, total: 4,
    sessions: [
      { day: 'Mon', type: 'Upper', status: 'completed', exercises: 'Bench 215x4, OHP 130x7, Rows 170x8', recovery: 81, strain: 15.0, duration: 63 },
      { day: 'Wed', type: 'Lower', status: 'completed', exercises: 'Squat 305x3, RDL 250x6, Leg Press 390x8', recovery: 67, strain: 17.0, duration: 74 },
      { day: 'Fri', type: 'Upper', status: 'completed', exercises: 'Bench 220x3, OHP 135x6, Rows 175x7', recovery: 74, strain: 15.2, duration: 62 },
      { day: 'Sat', type: 'Lower', status: 'completed', exercises: 'Squat 310x3, RDL 255x6, Leg Curl 3x12', recovery: 70, strain: 16.8, duration: 69 },
    ],
  },
  {
    number: 6, label: 'Week 6', completed: 1, total: 4,
    sessions: [
      { day: 'Mon', type: 'Upper', status: 'completed', exercises: 'Bench 225x3, OHP 135x6, Rows 175x8', recovery: 79, strain: 15.4, duration: 64 },
      { day: 'Wed', type: 'Lower', status: 'today', exercises: 'Squat, RDL, Leg Press' },
      { day: 'Fri', type: 'Upper', status: 'upcoming' },
      { day: 'Sat', type: 'Lower', status: 'upcoming' },
    ],
  },
]

const PROGRAM = {
  name: 'Bench Focus',
  phase: 'Strength',
  currentWeek: 6,
  totalWeeks: 8,
  goal: '315 Bench',
}

export function History({ onNavigateWorkout }: HistoryProps) {
  const [activeSegment, setActiveSegment] = useState<Segment>('program')
  const [expandedWeeks, setExpandedWeeks] = useState<Set<number>>(
    () => new Set([PROGRAM.currentWeek])
  )

  const toggleWeek = (weekNum: number) => {
    setExpandedWeeks(prev => {
      const next = new Set(prev)
      if (next.has(weekNum)) {
        next.delete(weekNum)
      } else {
        next.add(weekNum)
      }
      return next
    })
  }

  const progressPercent = Math.round(
    (PROGRAM.currentWeek / PROGRAM.totalWeeks) * 100
  )

  return (
    <div className="history-screen">
      <div className="segmented-control">
        {(['program', 'workouts', 'prs'] as Segment[]).map(seg => (
          <button
            key={seg}
            className={`segment${activeSegment === seg ? ' active' : ''}`}
            onClick={() => setActiveSegment(seg)}
          >
            {seg === 'prs' ? 'PRs' : seg.charAt(0).toUpperCase() + seg.slice(1)}
          </button>
        ))}
      </div>

      {activeSegment === 'program' && (
        <div className="program-view">
          <div className="program-header">
            <h2 className="program-name">{PROGRAM.name}</h2>
            <div className="program-meta">
              <span className="program-phase">{PROGRAM.phase}</span>
              <span className="program-week">
                Week {PROGRAM.currentWeek} of {PROGRAM.totalWeeks}
              </span>
            </div>
            <span className="program-goal-badge">{PROGRAM.goal}</span>
            <div className="program-progress-bar">
              <div
                className="program-progress-fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          <div className="weeks-list">
            {MOCK_WEEKS.map(week => {
              const isExpanded = expandedWeeks.has(week.number)
              const isCurrent = week.number === PROGRAM.currentWeek
              return (
                <div
                  key={week.number}
                  className={`week-section${isCurrent ? ' current' : ''}`}
                >
                  <div
                    className="week-header"
                    onClick={() => toggleWeek(week.number)}
                  >
                    <span className="week-arrow">
                      {isExpanded ? '\u25BC' : '\u25B6'}
                    </span>
                    <span className="week-label">{week.label}</span>
                    <span className="week-completion">
                      {week.completed}/{week.total}
                      {week.completed === week.total ? ' \u2713' : ''}
                    </span>
                  </div>

                  {isExpanded && (
                    <div className="week-sessions">
                      {week.sessions.map((session, i) => (
                        <div
                          key={i}
                          className={`session-card ${session.status}`}
                        >
                          <div className="session-card-content">
                            <div className="session-card-top">
                              <span className="session-day">{session.day}</span>
                              <span className="session-type">{session.type}</span>
                            </div>
                            {session.exercises && (
                              <p className="session-exercises">
                                {session.exercises}
                              </p>
                            )}
                            {session.status === 'completed' && (
                              <div className="session-whoop">
                                {session.recovery != null && (
                                  <span className="session-stat">
                                    {session.recovery}% rec
                                  </span>
                                )}
                                {session.strain != null && (
                                  <span className="session-stat">
                                    {session.strain} strain
                                  </span>
                                )}
                                {session.duration != null && (
                                  <span className="session-stat">
                                    {session.duration}min
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                          {session.status === 'today' && onNavigateWorkout && (
                            <button
                              className="session-go-btn"
                              onClick={onNavigateWorkout}
                            >
                              GO
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {activeSegment === 'workouts' && (
        <div className="placeholder-view">
          <p className="placeholder-text">Coming soon</p>
        </div>
      )}

      {activeSegment === 'prs' && (
        <div className="placeholder-view">
          <p className="placeholder-text">Coming soon</p>
        </div>
      )}
    </div>
  )
}
