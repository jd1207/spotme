import { useState, useEffect } from 'react'
import { api } from '../api'
import type { WhoopStats } from '../types'

interface ProfileProps {
  onReplayTutorial?: () => void
}

export function Profile({ onReplayTutorial }: ProfileProps) {
  const [whoopConnected, setWhoopConnected] = useState<boolean | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState('')
  const [todayStats, setTodayStats] = useState<WhoopStats | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)

  const fetchLatest = async () => {
    try {
      const result = await api.whoopLatest()
      setTodayStats(result.data)
    } catch { /* ignore */ }
  }

  const doSync = async () => {
    setSyncing(true)
    setSyncResult('')
    try {
      const result = await api.syncWhoop()
      if ('error' in result) {
        setSyncResult(String((result as Record<string, unknown>).error))
      } else {
        const warns = (result as Record<string, unknown>).warnings as string[] | undefined
        const parts = [`Synced ${result.synced} entries`]
        if (warns?.length) parts.push(warns[0])
        setSyncResult(parts.join(' — '))
        await fetchLatest()
      }
    } catch {
      setSyncResult('Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    api.whoopStatus()
      .then(s => {
        setWhoopConnected(s.connected)
        if (s.connected) fetchLatest()
      })
      .catch(() => {})
  }, [])

  const handleDisconnect = async () => {
    try {
      await api.whoopDisconnect()
      setWhoopConnected(false)
      setTodayStats(null)
      setSyncResult('Disconnected')
    } catch {
      setSyncResult('Disconnect failed')
    }
  }

  const handleLogin = async () => {
    if (!email || !password) return
    setLoggingIn(true)
    setSyncResult('')
    try {
      const result = await api.whoopLogin(email, password)
      if (result.connected || result.success) {
        setWhoopConnected(true)
        setEmail('')
        setPassword('')
        setSyncResult('Connected! Syncing...')
        setTimeout(() => doSync(), 500)
      } else {
        setSyncResult(result.error || 'Login failed')
      }
    } catch {
      setSyncResult('Login failed')
    } finally {
      setLoggingIn(false)
    }
  }

  const stat = (label: string, value: number | null, unit: string) => (
    <div className="whoop-stat-row">
      <span className="whoop-stat-label">{label}</span>
      <span className="whoop-stat-val">
        {value != null ? `${label === 'Strain' ? value.toFixed(1) : Math.round(value)}${unit}` : '—'}
      </span>
    </div>
  )

  return (
    <div className="profile-screen">
      <h2 className="profile-title">Profile</h2>

      <div className="profile-section">
        <h3 className="profile-section-title">Whoop</h3>
        <div className="profile-item">
          <span className="profile-item-label">Status</span>
          <span className={`profile-item-value ${whoopConnected ? 'connected' : ''}`}>
            {whoopConnected === null ? 'Checking...' : whoopConnected ? 'Connected' : 'Not connected'}
          </span>
        </div>

        {!whoopConnected && whoopConnected !== null && (
          <div className="whoop-login-form">
            <span className="profile-item-hint">
              Connect to sync workouts, track recovery, and get coaching adjusted to your body.
            </span>
            <input
              className="whoop-input"
              type="email"
              placeholder="Whoop email"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
            <input
              className="whoop-input"
              type="password"
              placeholder="Whoop password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
            />
            <button className="profile-sync-btn" onClick={handleLogin} disabled={loggingIn}>
              {loggingIn ? 'Connecting...' : 'Connect Whoop'}
            </button>
            <span className="profile-item-hint" style={{fontSize: '0.75rem', opacity: 0.6}}>
              Password is used once to authenticate, then discarded.
            </span>
          </div>
        )}

        {whoopConnected && (
          <>
            {todayStats && (
              <div className="whoop-today-stats">
                {stat('Recovery', todayStats.recovery_score, '%')}
                {stat('HRV', todayStats.hrv, ' ms')}
                {stat('Sleep', todayStats.sleep_score, '%')}
                {stat('Strain', todayStats.strain, '')}
                {stat('RHR', todayStats.resting_hr, ' bpm')}
              </div>
            )}
            <div className="profile-item">
              <button className="profile-sync-btn" onClick={() => doSync()} disabled={syncing}>
                {syncing ? 'Syncing...' : 'Sync Now'}
              </button>
            </div>
            <div className="profile-item">
              <button className="profile-action-btn" onClick={handleDisconnect}>
                Disconnect
              </button>
            </div>
          </>
        )}
        {syncResult && (
          <div className="profile-item">
            <span className="profile-sync-result">{syncResult}</span>
          </div>
        )}
      </div>

      <div className="profile-section">
        <h3 className="profile-section-title">App</h3>
        {onReplayTutorial && (
          <div className="profile-item">
            <button className="profile-action-btn" onClick={onReplayTutorial}>
              Replay Tutorial
            </button>
          </div>
        )}
        <div className="profile-item">
          <span className="profile-item-label">Version</span>
          <span className="profile-item-value">SpotMe v0.1.0</span>
        </div>
      </div>
    </div>
  )
}
