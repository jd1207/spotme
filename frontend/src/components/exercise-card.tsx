export function ExerciseCard({ name, sets, reps, weight }: { name: string; sets: number; reps: number; weight: number }) {
  return (
    <div className="exercise-card">
      <h3>{name}</h3>
      <p>{sets}x{reps} @ {weight}lbs</p>
    </div>
  )
}
