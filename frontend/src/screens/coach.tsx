import { useState } from 'react'
import { api } from '../api'
import { useVoice } from '../hooks/use-voice'
import { ChatBubble } from '../components/chat-bubble'

interface Message { role: string; content: string }

export function Coach() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const { transcript, listening, start, stop } = useVoice()
  const send = async (text: string) => {
    if (!text.trim()) return
    setMessages(m => [...m, { role: 'user', content: text }]); setInput('')
    const result = await api.chat(text)
    setMessages(m => [...m, { role: 'assistant', content: result.response }])
  }
  return (
    <div className="coach-screen">
      <div className="messages">{messages.map((m, i) => <ChatBubble key={i} role={m.role} content={m.content} />)}</div>
      <div className="input-bar">
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && send(input)} placeholder="Ask your coach..." />
        <button onClick={() => send(input)}>Send</button>
        <button className={`mic ${listening ? 'active' : ''}`} onMouseDown={start} onMouseUp={() => { stop(); if (transcript) send(transcript) }}>Mic</button>
      </div>
    </div>
  )
}
