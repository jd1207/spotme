import { useEffect, useState } from 'react'
import { api } from '../api'
import { LayoutRenderer } from '../components/layout-renderer'
import type { Layout, LayoutComponent } from '../types'
import { offlineDB } from '../db'

export function Dashboard() {
  const [layout, setLayout] = useState<LayoutComponent[]>([])
  useEffect(() => {
    api.getLayout('dashboard')
      .then(data => { setLayout(data.layout); offlineDB.cacheLayout(data) })
      .catch(async () => {
        const cached = await offlineDB.getCachedLayout('dashboard')
        if (cached) setLayout((cached as Layout).layout)
      })
  }, [])
  return <LayoutRenderer layout={layout} />
}
