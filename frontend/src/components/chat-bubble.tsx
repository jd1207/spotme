import type { SetSuggestion } from '../types'
import { SetCard } from './set-card'

interface ChatBubbleProps {
  role: string
  content: string
  setCard?: SetSuggestion
  onSetStart?: () => void
}

export function ChatBubble({ role, content, setCard, onSetStart }: ChatBubbleProps) {
  return (
    <div className={`chat-bubble ${role}`}>
      {role === 'assistant' && <span className="claude-label">CLAUDE</span>}
      <p>{content}</p>
      {setCard && (
        <SetCard
          exercise={setCard.exercise}
          weight={setCard.weight}
          reps={setCard.reps}
          basis={setCard.basis}
          onStart={onSetStart}
        />
      )}
    </div>
  )
}
