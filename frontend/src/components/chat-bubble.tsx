export function ChatBubble({ role, content }: { role: string; content: string }) {
  return (
    <div className={`chat-bubble ${role}`}>
      <p>{content}</p>
    </div>
  )
}
