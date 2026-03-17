import { useState, useEffect } from 'react'
import { api } from '../api'
import { MiniChart } from '../components/mini-chart'
import type { ProgressData } from '../types'

export function Progress() {
  const [data, setData] = useState<ProgressData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getProgress()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="progress-screen">
        <p className="placeholder-text">Loading...</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="progress-screen">
        <p className="placeholder-text">Could not load progress data.</p>
      </div>
    )
  }

  const hasAny =
    data.e1rm_trend.length > 0 ||
    data.volume_trend.length > 0 ||
    data.whoop.recovery.length > 0

  if (!hasAny) {
    return (
      <div className="progress-screen">
        <h2 className="progress-title">Progress</h2>
        <p className="placeholder-text">
          Complete a few workouts to see trends here.
        </p>
      </div>
    )
  }

  return (
    <div className="progress-screen">
      <h2 className="progress-title">30-Day Trends</h2>
      <MiniChart
        data={data.e1rm_trend}
        valueKey="e1rm"
        label="Estimated 1RM"
        unit=" lbs"
        color="var(--accent)"
      />
      <MiniChart
        data={data.volume_trend}
        valueKey="volume"
        label="Total Volume"
        unit=" lbs"
        color="var(--success)"
      />
      <MiniChart
        data={data.whoop.recovery}
        valueKey="value"
        label="Recovery"
        unit="%"
        color="var(--success)"
      />
      <MiniChart
        data={data.whoop.hrv}
        valueKey="value"
        label="HRV"
        unit=" ms"
        color="var(--info)"
      />
      <MiniChart
        data={data.whoop.strain}
        valueKey="value"
        label="Strain"
        unit=""
        color="#f5a623"
      />
    </div>
  )
}
