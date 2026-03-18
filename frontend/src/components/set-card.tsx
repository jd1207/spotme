import { useState, useEffect, useRef } from 'react'
import type { PlannedSet, SetProgress } from '../types'

const REST_BY_FEEL: Record<string, number> = { easy: 90, solid: 120, tough: 150, max: 180 }
const WARMUP_REST = 90

interface SetCardProps {
  currentSet: PlannedSet
  progress: SetProgress
  nextPreview: string | null
  onComplete: (weight: number, reps: number, feel: string | null) => void
  onSkip: () => void
}

type CardState = 'ready' | 'feedback' | 'resting'

export function SetCard({ currentSet, progress, nextPreview, onComplete, onSkip }: SetCardProps) {
  const [state, setState] = useState<CardState>('ready')
  const [restSeconds, setRestSeconds] = useState(0)
  const [completedWeight, setCompletedWeight] = useState(currentSet.weight)
  const [completedReps, setCompletedReps] = useState(currentSet.reps)
  const timerRef = useRef<number | null>(null)

  // reset state when currentSet changes
  useEffect(() => {
    setState('ready')
    setCompletedWeight(currentSet.weight)
    setCompletedReps(currentSet.reps)
    if (timerRef.current) clearInterval(timerRef.current)
  }, [currentSet.id])

  // rest timer countdown
  useEffect(() => {
    if (state !== 'resting' || restSeconds <= 0) return
    timerRef.current = window.setInterval(() => {
      setRestSeconds(prev => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [state, restSeconds > 0])

  const handleDone = () => {
    if (currentSet.set_type === 'warmup') {
      // warm-ups skip feedback, auto-complete with no feel
      onComplete(completedWeight, completedReps, null)
      setRestSeconds(WARMUP_REST)
      setState('resting')
    } else {
      setState('feedback')
    }
  }

  const handleFeel = (feel: string) => {
    onComplete(completedWeight, completedReps, feel)
    setRestSeconds(REST_BY_FEEL[feel] || 120)
    setState('resting')
  }

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`

  const setLabel = currentSet.set_type === 'warmup'
    ? `Warm-up ${currentSet.set_number} of ${currentSet.total_of_type}`
    : `Set ${currentSet.set_number} of ${currentSet.total_of_type}`

  // state 1: ready
  if (state === 'ready') {
    return (
      <div className="set-card-sticky">
        <div className="set-card-header">
          <span className="set-card-exercise">{currentSet.exercise}</span>
          <span className="set-card-label">{setLabel}</span>
        </div>
        <span className="set-card-prescription">{completedWeight} x {completedReps}</span>
        <div className="set-card-actions">
          <button className="set-card-skip" onClick={onSkip}>Skip</button>
          <button className="set-card-done" onClick={handleDone}>Done</button>
        </div>
        <span className="set-card-progress">{progress.completed}/{progress.total} sets</span>
      </div>
    )
  }

  // state 2: feedback (working sets only)
  if (state === 'feedback') {
    return (
      <div className="set-card-sticky">
        <span className="set-card-done-text">Done — {completedWeight} x {completedReps}</span>
        <span className="set-card-feel-prompt">How'd that feel?</span>
        <div className="set-card-feel-buttons">
          {['easy', 'solid', 'tough', 'max'].map(f => (
            <button key={f} className={`set-card-feel set-card-feel-${f}`} onClick={() => handleFeel(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>
    )
  }

  // state 3: resting
  return (
    <div className="set-card-sticky">
      <div className="set-card-rest-top">
        <span className="set-card-done-text">Done — {completedWeight} x {completedReps}</span>
        {restSeconds > 0 && <span className="set-card-timer">{formatTime(restSeconds)}</span>}
      </div>
      {nextPreview && <span className="set-card-next">NEXT: {nextPreview}</span>}
      <div className="set-card-actions">
        <button className="set-card-skip" onClick={() => { setRestSeconds(prev => prev + 30) }}>+30s</button>
        <button className="set-card-done" onClick={() => { setRestSeconds(0) }}>Skip Rest</button>
      </div>
    </div>
  )
}
