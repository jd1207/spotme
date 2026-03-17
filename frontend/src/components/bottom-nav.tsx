interface BottomNavProps {
  active: string
  onChange: (tab: string) => void
}

const tabs = [
  { id: 'workout', label: 'Workout', icon: '\u2687' },
  { id: 'program', label: 'Program', icon: '\u2630' },
  { id: 'profile', label: 'Profile', icon: '\u2699' },
]

export function BottomNav({ active, onChange }: BottomNavProps) {
  return (
    <nav className="bottom-nav">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`bottom-nav-tab${active === tab.id ? ' active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          <span className="bottom-nav-icon">{tab.icon}</span>
          <span className="bottom-nav-label">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
