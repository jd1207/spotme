import type { SetSuggestion } from '../types'
import { SetCard } from './set-card'

interface ChatBubbleProps {
  role: string
  content: string
  setCard?: SetSuggestion
  onSetStart?: () => void
}

function formatContent(text: string) {
  // split into paragraphs, handle basic markdown
  return text.split('\n').map((line, i) => {
    if (!line.trim()) return <br key={i} />
    // bold: **text**
    const parts = line.split(/(\*\*[^*]+\*\*)/g).map((part, j) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={j}>{part.slice(2, -2)}</strong>
      }
      return part
    })
    // bullet points
    const trimmed = line.trim()
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      return <div key={i} className="chat-list-item">{parts}</div>
    }
    return <div key={i}>{parts}</div>
  })
}

export function ChatBubble({ role, content, setCard, onSetStart }: ChatBubbleProps) {
  return (
    <div className={`chat-bubble ${role}`}>
      {role === 'assistant' && <span className="claude-label">CLAUDE</span>}
      <div className="chat-content">{formatContent(content)}</div>
      {setCard && (
        <SetCard
          exercise={setCard.exercise}
          weight={setCard.weight}
          reps={setCard.reps}
          basis={setCard.basis}
          lastSet={setCard.lastSet}
          onStart={onSetStart}
        />
      )}
    </div>
  )
}
