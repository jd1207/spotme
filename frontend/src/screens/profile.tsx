import { useState } from 'react'
import { api } from '../api'

interface ProfileProps {
  onReplayTutorial?: () => void
}

export function Profile({ onReplayTutorial }: ProfileProps) {
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState('')

  const handleSync = async () => {
    setSyncing(true)
    setSyncResult('')
    try {
      const result = await api.syncWhoop()
      setSyncResult(`Synced ${result.synced} workout${result.synced !== 1 ? 's' : ''}`)
    } catch {
      setSyncResult('Sync failed — try again later')
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
          <span className="profile-item-label">Connection</span>
          <span className="profile-item-value">Connected</span>
        </div>
        <div className="profile-item">
          <button
            className="profile-sync-btn"
            onClick={handleSync}
            disabled={syncing}
          >
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
          {syncResult && (
            <span className="profile-sync-result">{syncResult}</span>
          )}
        </div>
      </div>

      <div className="profile-section">
        <h3 className="profile-section-title">App</h3>
        {onReplayTutorial && (
          <div className="profile-item">
            <button
              className="profile-action-btn"
              onClick={onReplayTutorial}
            >
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
