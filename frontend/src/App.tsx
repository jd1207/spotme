import { useState } from 'react'
import { Dashboard } from './screens/dashboard'
import { WorkoutSession } from './screens/workout-session'
import { Coach } from './screens/coach'
import { ProgramOverview } from './screens/program'
import { Progress } from './screens/progress'
import { useOffline } from './hooks/use-offline'

type Screen = 'dashboard' | 'workout' | 'coach' | 'program' | 'progress'
const SCREENS: Record<Screen, React.FC> = { dashboard: Dashboard, workout: WorkoutSession, coach: Coach, program: ProgramOverview, progress: Progress }

export default function App() {
  const [screen, setScreen] = useState<Screen>('dashboard')
  const { online } = useOffline()
  const ActiveScreen = SCREENS[screen]
  return (
    <div className="app">
      {!online && <div className="offline-banner">offline — data will sync when connected</div>}
      <ActiveScreen />
      <nav className="bottom-nav">
        <button className={screen === 'dashboard' ? 'active' : ''} onClick={() => setScreen('dashboard')}>Home</button>
        <button className={screen === 'workout' ? 'active' : ''} onClick={() => setScreen('workout')}>Workout</button>
        <button className={screen === 'coach' ? 'active' : ''} onClick={() => setScreen('coach')}>Coach</button>
        <button className={screen === 'program' ? 'active' : ''} onClick={() => setScreen('program')}>Program</button>
        <button className={screen === 'progress' ? 'active' : ''} onClick={() => setScreen('progress')}>Progress</button>
      </nav>
    </div>
  )
}
