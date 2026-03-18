import { useState, useEffect } from 'react'
import { Workout } from './screens/workout'
import { History } from './screens/history'
import { Diet } from './screens/diet'
import { Profile } from './screens/profile'
import { Onboarding } from './components/onboarding'
import { Intake } from './components/intake'
import { BottomNav } from './components/bottom-nav'
import { useOffline } from './hooks/use-offline'
import { api } from './api'

type Tab = 'workout' | 'program' | 'diet' | 'profile'

export default function App() {
  const [onboarded, setOnboarded] = useState(
    () => localStorage.getItem('spotme_onboarded') === '1'
  )
  const [intakeDone, setIntakeDone] = useState(
    () => localStorage.getItem('spotme_intake_done') === '1'
  )
  const [loading, setLoading] = useState(!intakeDone)
  const [tab, setTab] = useState<Tab>('workout')
  const { online } = useOffline()

  // check server for existing profile so we skip intake even if localStorage was cleared
  useEffect(() => {
    if (intakeDone) { setLoading(false); return }
    api.getProfile()
      .then(p => {
        if (p && p.name) {
          localStorage.setItem('spotme_intake_done', '1')
          setIntakeDone(true)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [intakeDone])

  if (!onboarded) {
    return <Onboarding onComplete={() => setOnboarded(true)} />
  }

  if (loading) return null

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
      {tab === 'program' && (
        <History onNavigateWorkout={() => setTab('workout')} />
      )}
      {tab === 'diet' && <Diet />}
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
