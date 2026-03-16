import { useState } from 'react'

export function SetLogger({ exercise, set_number, onLog }: { exercise: string; set_number: number; onLog?: (data: object) => void }) {
  const [weight, setWeight] = useState('')
  const [reps, setReps] = useState('')
  const [rpe, setRpe] = useState('')
  const handleSubmit = () => { onLog?.({ exercise, set_number, weight: Number(weight), reps: Number(reps), rpe: Number(rpe) || undefined }) }
  return (
    <div className="set-logger">
      <span className="set-label">Set {set_number}</span>
      <input type="number" placeholder="lbs" value={weight} onChange={(e) => setWeight(e.target.value)} />
      <input type="number" placeholder="reps" value={reps} onChange={(e) => setReps(e.target.value)} />
      <input type="number" placeholder="RPE" value={rpe} onChange={(e) => setRpe(e.target.value)} step="0.5" />
      <button onClick={handleSubmit}>Log</button>
    </div>
  )
}
