import { useState, useEffect } from 'react'
import { api } from '../api'

interface ProgramData {
  has_program: boolean
  content: string | null
  stats: {
    total_workouts: number
    completed_workouts: number
    today: string
  } | null
}

export function ProgramView() {
  const [data, setData] = useState<ProgramData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getProgram()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="placeholder-text">Loading program...</p>
  if (!data?.has_program) return (
    <div className="placeholder-view">
      <p className="placeholder-text">No program loaded yet.</p>
      <p className="placeholder-text">Chat with Claude to set up your training plan.</p>
    </div>
  )

  return (
    <div className="program-view">
      {data.stats && (
        <div className="program-stats">
          <span className="program-stat">
            {data.stats.completed_workouts} workouts completed
          </span>
        </div>
      )}
      <div className="program-content">
        {renderMarkdown(data.content!)}
      </div>
    </div>
  )
}

function renderMarkdown(md: string) {
  const sections = md.split(/^## /m).filter(Boolean)
  return sections.map((section, i) => {
    const lines = section.split('\n')
    const title = lines[0]?.trim()
    const body = lines.slice(1).join('\n').trim()
    return (
      <div key={i} className="program-section">
        {title && <h3 className="program-section-title">{title}</h3>}
        <div className="program-section-body">
          {renderBody(body)}
        </div>
      </div>
    )
  })
}

function renderBody(text: string) {
  const lines = text.split('\n')
  return lines.map((line, i) => {
    const trimmed = line.trim()
    if (!trimmed) return null
    if (trimmed.startsWith('### ')) {
      return <h4 key={i} className="program-week-header">{trimmed.slice(4)}</h4>
    }
    if (trimmed.startsWith('- ')) {
      const content = trimmed.slice(2)
      const formatted = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      return (
        <div key={i} className="program-item">
          <span className="program-bullet">·</span>
          <span dangerouslySetInnerHTML={{ __html: formatted }} />
        </div>
      )
    }
    const formatted = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    return (
      <p key={i} className="program-text"
        dangerouslySetInnerHTML={{ __html: formatted }} />
    )
  })
}
