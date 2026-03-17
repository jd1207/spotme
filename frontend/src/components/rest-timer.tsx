import { useState, useEffect, useRef } from 'react'

interface RestTimerProps {
  seconds: number
  compact?: boolean
  onComplete?: () => void
}

export function RestTimer({ seconds, compact, onComplete }: RestTimerProps) {
  const [remaining, setRemaining] = useState(seconds)
  const [active, setActive] = useState(false)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    if (!active || remaining <= 0) return
    const timer = setInterval(() => setRemaining((r) => r - 1), 1000)
    return () => clearInterval(timer)
  }, [active, remaining])

  useEffect(() => {
    if (active && remaining <= 0) {
      setActive(false)
      onCompleteRef.current?.()
    }
  }, [active, remaining])

  const minutes = Math.floor(remaining / 60)
  const secs = remaining % 60
  const timeText = `${minutes}:${secs.toString().padStart(2, '0')}`

  if (compact) {
    return (
      <span className="rest-timer compact">
        <span className="time">{timeText}</span>
      </span>
    )
  }

  return (
    <div className="rest-timer">
      <span className="time">{timeText}</span>
      <button
        onClick={() => {
          setActive(!active)
          if (!active) setRemaining(seconds)
        }}
      >
        {active ? 'Reset' : 'Start Rest'}
      </button>
    </div>
  )
}
