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
    const id = setInterval(() => {
      setRemaining(prev => {
        if (prev <= 1) {
          setActive(false)
          onCompleteRef.current?.()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [active])

  // sync if parent changes seconds prop
  useEffect(() => {
    if (!active) setRemaining(seconds)
  }, [seconds])

  const toggle = () => setActive(!active)
  const reset = () => { setActive(false); setRemaining(seconds) }
  const addTime = (s: number) => setRemaining(prev => prev + s)

  const mins = Math.floor(remaining / 60)
  const secs = remaining % 60
  const display = `${mins}:${secs.toString().padStart(2, '0')}`

  if (compact) return <span className="rest-timer-compact">{display}</span>

  const label = active ? 'Pause' : remaining < seconds ? 'Resume' : 'Start'

  return (
    <div className="rest-timer">
      <span className="rest-timer-display">{display}</span>
      <div className="rest-timer-controls">
        <button className="rest-btn" onClick={toggle}>{label}</button>
        <button className="rest-btn rest-btn-add" onClick={() => addTime(30)}>+30s</button>
        <button className="rest-btn rest-btn-reset" onClick={reset}>Reset</button>
      </div>
    </div>
  )
}
