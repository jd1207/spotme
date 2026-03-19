import { useState, useEffect } from 'react'
import { Workout } from './screens/workout'
import { History } from './screens/history'
import { Diet } from './screens/diet'
import { Profile } from './screens/profile'
import { Onboarding } from './components/onboarding'
import { BottomNav } from './components/bottom-nav'
import { useOffline } from './hooks/use-offline'
import { api } from './api'

type Tab = 'workout' | 'program' | 'diet' | 'profile'

export default function App() {
  const [ready, setReady] = useState(
    () => localStorage.getItem('spotme_intake_done') === '1'
  )
  const [loading, setLoading] = useState(!ready)
  const [tab, setTab] = useState<Tab>('workout')
  const { online } = useOffline()

  // check server for existing profile so we skip onboarding even if localStorage was cleared
  useEffect(() => {
    if (ready) { setLoading(false); return }
    api.getProfile()
      .then(p => {
        if (p && p.name) {
          localStorage.setItem('spotme_intake_done', '1')
          localStorage.setItem('spotme_onboarded', '1')
          setReady(true)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [ready])

  if (loading) return null

  if (!ready) {
    return <Onboarding onComplete={() => setReady(true)} />
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
            setReady(false)
          }}
        />
      )}
      <BottomNav active={tab} onChange={(t) => setTab(t as Tab)} />
    </div>
  )
}
