import { useState, useEffect } from 'react'
import { api } from '../api'

interface ProfileProps {
  onReplayTutorial?: () => void
}

export function Profile({ onReplayTutorial }: ProfileProps) {
  const [whoopConnected, setWhoopConnected] = useState<boolean | null>(null)
  const [oauthAvailable, setOauthAvailable] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState('')
  const [connecting, setConnecting] = useState(false)

  useEffect(() => {
    // check connection on url params (after OAuth redirect)
    const params = new URLSearchParams(window.location.search)
    if (params.get('whoop') === 'connected') {
      setWhoopConnected(true)
      setSyncResult('Whoop connected!')
      window.history.replaceState({}, '', '/')
    }
    api.whoopStatus()
      .then(s => { setWhoopConnected(s.connected); setOauthAvailable(s.oauth_available) })
      .catch(() => {})
  }, [])

  const connectWhoop = async () => {
    setConnecting(true)
    try {
      const result = await api.whoopAuthorize()
      if (result.url) {
        window.location.href = result.url
      } else {
        setSyncResult(result.error || 'Could not start Whoop connection')
        setConnecting(false)
      }
    } catch {
      setSyncResult('Connection failed')
      setConnecting(false)
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
        {!whoopConnected && oauthAvailable && (
          <div className="profile-item">
            <button className="profile-connect-btn" onClick={connectWhoop} disabled={connecting}>
              {connecting ? 'Redirecting...' : 'Connect Whoop'}
            </button>
          </div>
        )}
        {!whoopConnected && !oauthAvailable && whoopConnected !== null && (
          <div className="profile-item">
            <span className="profile-item-hint">Add WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET to .env to enable</span>
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
