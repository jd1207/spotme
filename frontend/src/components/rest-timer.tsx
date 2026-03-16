import { useState, useEffect } from 'react'

export function RestTimer({ seconds }: { seconds: number }) {
  const [remaining, setRemaining] = useState(seconds)
  const [active, setActive] = useState(false)
  useEffect(() => {
    if (!active || remaining <= 0) return
    const timer = setInterval(() => setRemaining(r => r - 1), 1000)
    return () => clearInterval(timer)
  }, [active, remaining])
  const minutes = Math.floor(remaining / 60)
  const secs = remaining % 60
  return (
    <div className="rest-timer">
      <span className="time">{minutes}:{secs.toString().padStart(2, '0')}</span>
      <button onClick={() => { setActive(!active); if (!active) setRemaining(seconds) }}>{active ? 'Reset' : 'Start Rest'}</button>
    </div>
  )
}
