interface SetCardProps {
  exercise: string
  weight: number
  reps: number
  basis?: string
  onStart?: () => void
}

export function SetCard({ exercise, weight, reps, basis, onStart }: SetCardProps) {
  return (
    <div className="set-card">
      <span className="set-card-label">NEXT SET</span>
      <span className="set-card-exercise">{exercise}</span>
      <span className="set-card-prescription">{weight} lbs x {reps}</span>
      {basis && <span className="set-card-basis">{basis}</span>}
      <button className="set-card-start" onClick={onStart}>
        Start Set
      </button>
    </div>
  )
}
