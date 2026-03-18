interface ChatBubbleProps {
  role: string
  content: string
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

export function ChatBubble({ role, content }: ChatBubbleProps) {
  return (
    <div className={`chat-bubble ${role}`}>
      {role === 'assistant' && <span className="claude-label">CLAUDE</span>}
      <div className="chat-content">{formatContent(content)}</div>
    </div>
  )
}
