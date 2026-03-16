import { useEffect, useState } from 'react'
import { api } from '../api'
import { LayoutRenderer } from '../components/layout-renderer'
import type { LayoutComponent } from '../types'

export function WorkoutSession() {
  const [layout, setLayout] = useState<LayoutComponent[]>([])
  useEffect(() => {
    api.getLayout('workout_session').then(data => setLayout(data.layout)).catch(() => {})
  }, [])
  return <LayoutRenderer layout={layout} />
}
