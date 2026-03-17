import { useState, useEffect } from 'react'
import { api } from '../api'
import type { WhoopStats } from '../types'

interface ProfileProps {
  onReplayTutorial?: () => void
}

export function Profile({ onReplayTutorial }: ProfileProps) {
  const [whoopConnected, setWhoopConnected] = useState<boolean | null>(null)
  const [oauthAvailable, setOauthAvailable] = useState(false)
  const [writeEnabled, setWriteEnabled] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [todayStats, setTodayStats] = useState<WhoopStats | null>(null)
  const [testingWrite, setTestingWrite] = useState(false)
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
        setOauthAvailable(s.oauth_available)
        setWriteEnabled(s.write_enabled)
        if (s.connected) fetchLatest()
      })
      .catch(() => {})

    const params = new URLSearchParams(window.location.search)
    const whoopParam = params.get('whoop')
    if (whoopParam === 'connected') {
      setWhoopConnected(true)
      setSyncResult('Whoop connected! Syncing...')
      window.history.replaceState({}, '', '/')
      setTimeout(() => doSync(), 500)
    } else if (whoopParam === 'error') {
      setSyncResult(`Connection failed: ${params.get('reason') || 'unknown'}`)
      window.history.replaceState({}, '', '/')
    }
  }, [])

  const handleConnect = async () => {
    setConnecting(true)
    try {
      const result = await api.whoopAuthorize()
      if (result.url) {
        window.location.href = result.url
      } else {
        setSyncResult(result.error || 'OAuth not configured')
        setConnecting(false)
      }
    } catch {
      setSyncResult('Failed to start OAuth')
      setConnecting(false)
    }
  }

  const handleDisconnect = async () => {
    try {
      await api.whoopDisconnect()
      setWhoopConnected(false)
      setWriteEnabled(false)
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
      if (result.success) {
        setWriteEnabled(true)
        setEmail('')
        setPassword('')
        setSyncResult('Write access enabled!')
      } else {
        setSyncResult(result.error || 'Login failed')
      }
    } catch {
      setSyncResult('Login failed')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleTestWrite = async () => {
    setTestingWrite(true)
    setSyncResult('')
    try {
      const result = await api.whoopTestWrite()
      if (result.success) {
        setSyncResult('Wrote to Whoop! Check your app for a 1-min stretching activity')
      } else {
        setSyncResult(result.error || 'Write failed')
      }
    } catch {
      setSyncResult('Write test failed')
    } finally {
      setTestingWrite(false)
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

        {!whoopConnected && oauthAvailable && whoopConnected !== null && (
          <div className="profile-item">
            <button className="profile-connect-btn" onClick={handleConnect} disabled={connecting}>
              {connecting ? 'Redirecting...' : 'Connect Whoop'}
            </button>
          </div>
        )}

        {!whoopConnected && !oauthAvailable && whoopConnected !== null && (
          <div className="profile-item">
            <span className="profile-item-value">OAuth not configured</span>
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

            {writeEnabled ? (
              <div className="profile-item">
                <button className="profile-test-btn" onClick={handleTestWrite} disabled={testingWrite}>
                  {testingWrite ? 'Writing...' : 'Test Write to Whoop'}
                </button>
              </div>
            ) : (
              <div className="whoop-login-form">
                <span className="profile-item-hint">
                  Enter Whoop login to enable writing workouts
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
                  {loggingIn ? 'Logging in...' : 'Enable Write Access'}
                </button>
              </div>
            )}

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
