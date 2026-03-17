interface RecoveryBannerProps {
  recovery: number | null
  hrv: number | null
  sleep: number | null
  strain: number | null
}

function getZone(score: number | null): { label: string; color: string } {
  if (score == null) return { label: 'No data', color: 'var(--text-disabled)' }
  if (score >= 67) return { label: 'Green', color: 'var(--success)' }
  if (score >= 34) return { label: 'Yellow', color: '#f5a623' }
  return { label: 'Red', color: '#e57373' }
}

export function RecoveryBanner({ recovery, hrv, sleep, strain }: RecoveryBannerProps) {
  const zone = getZone(recovery)
  return (
    <div className="recovery-banner" style={{ borderLeftColor: zone.color }}>
      <div className="recovery-zone">
        <span className="recovery-zone-dot" style={{ background: zone.color }} />
        <span className="recovery-zone-label">{zone.label}</span>
        <span className="recovery-zone-score">
          {recovery != null ? `${Math.round(recovery)}%` : '\u2014'}
        </span>
      </div>
      <div className="recovery-stats">
        <span>HRV {hrv != null ? Math.round(hrv) : '\u2014'}</span>
        <span>Sleep {sleep != null ? `${Math.round(sleep)}%` : '\u2014'}</span>
        <span>Strain {strain != null ? strain.toFixed(1) : '\u2014'}</span>
      </div>
    </div>
  )
}
