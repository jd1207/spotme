import { useState, useEffect, useCallback } from 'react'
import { offlineDB } from '../db'
import { api } from '../api'

export function useOffline() {
  const [online, setOnline] = useState(navigator.onLine)
  useEffect(() => {
    const handleOnline = () => { setOnline(true); syncOfflineData() }
    const handleOffline = () => setOnline(false)
    window.addEventListener('online', handleOnline); window.addEventListener('offline', handleOffline)
    return () => { window.removeEventListener('online', handleOnline); window.removeEventListener('offline', handleOffline) }
  }, [])
  const syncOfflineData = useCallback(async () => {
    const sets = await offlineDB.getOfflineSets()
    for (const set of sets) { try { await api.logSet(set as any) } catch { return } }
    await offlineDB.clearOfflineSets()
  }, [])
  return { online, syncOfflineData }
}
