interface SetCardProps {
  exercise: string
  weight: number
  reps: number
  basis?: string
  lastSet?: { weight: number; reps: number; rpe: number | null }
  onStart?: () => void
}

export function SetCard({ exercise, weight, reps, basis, lastSet, onStart }: SetCardProps) {
  return (
    <div className="set-card">
      <span className="set-card-label">NEXT SET</span>
      <span className="set-card-exercise">{exercise}</span>
      <span className="set-card-prescription">{weight} lbs x {reps}</span>
      {lastSet && (
        <span className="set-card-last">
          Last: {lastSet.weight}x{lastSet.reps}{lastSet.rpe ? ` @ RPE ${lastSet.rpe}` : ''}
        </span>
      )}
      {basis && <span className="set-card-basis">{basis}</span>}
      <button className="set-card-start" onClick={onStart}>
        Start Set
      </button>
    </div>
  )
}
