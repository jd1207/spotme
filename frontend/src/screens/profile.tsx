import { useState, useEffect } from 'react'
import { api } from '../api'

interface ProfileProps {
  onReplayTutorial?: () => void
}

export function Profile({ onReplayTutorial }: ProfileProps) {
  const [whoopConnected, setWhoopConnected] = useState<boolean | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)
  const [loginError, setLoginError] = useState('')
  const [showLogin, setShowLogin] = useState(false)

  useEffect(() => {
    api.whoopStatus()
      .then(s => setWhoopConnected(s.connected))
      .catch(() => {})
  }, [])

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) return
    setLoggingIn(true)
    setLoginError('')
    try {
      const result = await api.whoopLogin(email, password)
      if (result.connected) {
        setWhoopConnected(true)
        setShowLogin(false)
        setSyncResult('Whoop connected!')
      } else {
        setLoginError(result.error || 'Login failed')
      }
    } catch {
      setLoginError('Connection failed')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setSyncResult('')
    try {
      const result = await api.syncWhoop()
      if ('error' in result) {
        setSyncResult(String((result as Record<string, unknown>).error))
      } else {
        setSyncResult(`Synced ${result.synced} entries`)
      }
    } catch {
      setSyncResult('Sync failed')
    } finally {
      setSyncing(false)
    }
  }

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

        {!whoopConnected && !showLogin && whoopConnected !== null && (
          <div className="profile-item">
            <button className="profile-connect-btn" onClick={() => setShowLogin(true)}>
              Connect Whoop
            </button>
          </div>
        )}

        {showLogin && !whoopConnected && (
          <div className="whoop-login-form">
            <input
              className="whoop-input"
              type="email"
              placeholder="Whoop email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
            />
            <input
              className="whoop-input"
              type="password"
              placeholder="Whoop password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              autoComplete="current-password"
            />
            {loginError && <span className="whoop-login-error">{loginError}</span>}
            <button className="profile-connect-btn" onClick={handleLogin} disabled={loggingIn}>
              {loggingIn ? 'Connecting...' : 'Log In'}
            </button>
          </div>
        )}

        {whoopConnected && (
          <div className="profile-item">
            <button className="profile-sync-btn" onClick={handleSync} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>
            {syncResult && <span className="profile-sync-result">{syncResult}</span>}
          </div>
        )}
        {!whoopConnected && syncResult && (
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
