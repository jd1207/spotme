import { useState } from 'react'

interface SectionProps {
  title: string
  content: string
}

export function ProgramSection({ title, content }: SectionProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="program-section" onClick={() => setOpen(!open)}>
      <div className="program-section-header">
        <h3 className="program-section-title">{title}</h3>
        <span className="program-chevron">{open ? '\u25be' : '\u25b8'}</span>
      </div>
      {open && (
        <div className="program-section-body">
          {content.split('\n').filter(Boolean).map((line, i) => (
            <p key={i} className="program-text">{line.trim().replace(/^[-*] /, '')}</p>
          ))}
        </div>
      )}
    </div>
  )
}
