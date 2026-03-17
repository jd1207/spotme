import { useState } from 'react'
import { Workout } from './screens/workout'
import { History } from './screens/history'
import { Profile } from './screens/profile'
import { Onboarding } from './components/onboarding'
import { Intake } from './components/intake'
import { BottomNav } from './components/bottom-nav'
import { useOffline } from './hooks/use-offline'

type Tab = 'workout' | 'history' | 'profile'

export default function App() {
  const [onboarded, setOnboarded] = useState(
    () => localStorage.getItem('spotme_onboarded') === '1'
  )
  const [intakeDone, setIntakeDone] = useState(
    () => localStorage.getItem('spotme_intake_done') === '1'
  )
  const [tab, setTab] = useState<Tab>('workout')
  const { online } = useOffline()

  if (!onboarded) {
    return <Onboarding onComplete={() => setOnboarded(true)} />
  }

  if (!intakeDone) {
    return <Intake onComplete={() => setIntakeDone(true)} />
  }

  return (
    <div className="app">
      {!online && (
        <div className="offline-banner">
          Offline — sets will sync when connected
        </div>
      )}
      {tab === 'workout' && <Workout />}
      {tab === 'history' && (
        <History onNavigateWorkout={() => setTab('workout')} />
      )}
      {tab === 'profile' && (
        <Profile
          onReplayTutorial={() => {
            localStorage.removeItem('spotme_onboarded')
            localStorage.removeItem('spotme_intake_done')
            setOnboarded(false)
            setIntakeDone(false)
          }}
        />
      )}
      <BottomNav active={tab} onChange={(t) => setTab(t as Tab)} />
    </div>
  )
}
