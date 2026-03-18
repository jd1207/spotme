import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { ChatBubble } from '../components/chat-bubble'
import { RestTimer } from '../components/rest-timer'
import { ContextBanner } from '../components/context-banner'
import { DayList } from './workout-home'
import type { Message, SetSuggestion } from '../types'

const REST_DURATION = 120

function todayEastern(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}

// fallback: extract set suggestion from claude's text via regex
function extractSetFromText(text: string): SetSuggestion | undefined {
  const match = text.match(/(\d+)\s*(?:lbs?)?\s*[x\u00d7]\s*(\d+)/)
  if (!match) return undefined
  const exMatch = text.match(/(?:for|on|do)\s+([A-Z][a-z]+(?:\s+[A-Za-z]+){0,3})/i)
  return {
    exercise: exMatch ? exMatch[1] : 'Next Set',
    weight: parseInt(match[1]),
    reps: parseInt(match[2]),
    basis: 'Based on your feedback',
  }
}

function formatDateHeader(date: string): string {
  if (date === todayEastern()) return 'Today'
  const d = new Date(date + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

export function Workout() {
  const [activeWorkoutId, setActiveWorkoutId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [showRest, setShowRest] = useState(false)
  const [chatDate, setChatDate] = useState(todayEastern)
  const [showDayList, setShowDayList] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages, thinking, showRest])

  // load day messages when chatDate changes (and not in workout mode)
  useEffect(() => {
    if (activeWorkoutId) return
    api.getChatDay(chatDate)
      .then(r => {
        setMessages(r.messages.map(m => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
        })))
      })
      .catch(() => setMessages([]))
  }, [chatDate, activeWorkoutId])

  const endWorkout = async () => {
    if (activeWorkoutId && activeWorkoutId > 0) {
      try { await api.completeWorkout(activeWorkoutId) } catch {}
    }
    setActiveWorkoutId(null)
    setChatDate(todayEastern())
    setMessages([])
  }

  const handleSetStart = (suggestion: SetSuggestion) => {
    api.logSet({
      exercise_name: suggestion.exercise,
      weight: suggestion.weight,
      reps: suggestion.reps,
    }).catch(() => {})
    setShowRest(true)
  }

  const send = async (text: string) => {
    if (!text.trim()) return
    setMessages(m => [...m, { role: 'user', content: text }])
    setInput('')
    setThinking(true)
    try {
      const wid = activeWorkoutId && activeWorkoutId > 0 ? activeWorkoutId : undefined
      const dateParam = activeWorkoutId ? undefined : chatDate
      const result = await api.chat(text, wid, dateParam)
      const msg: Message = { role: 'assistant', content: result.response }
      const structured = result.set_suggestion
      msg.setCard = structured
        ? { exercise: structured.exercise, weight: structured.weight, reps: structured.reps, basis: structured.basis || 'Claude suggestion' }
        : extractSetFromText(result.response)
      if (msg.setCard) {
        try {
          const lastData = await api.getLastExercise(msg.setCard.exercise)
          if (lastData.sets.length > 0) msg.setCard.lastSet = lastData.sets[0]
        } catch { /* last set is a nice-to-have */ }
      }
      setMessages(m => [...m, msg])
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Connection error — try again in a sec.' }])
    } finally {
      setThinking(false)
    }
  }

  const selectDay = (date: string) => {
    setChatDate(date)
    setShowDayList(false)
  }

  // state B: day list
  if (!activeWorkoutId && showDayList) {
    return <DayList onSelectDay={selectDay} />
  }

  // state C: active workout (preserved)
  if (activeWorkoutId) {
    return (
      <div className="coach-screen">
        <div className="workout-chat-header">
          <button className="end-workout-btn" onClick={endWorkout}>End</button>
          <span className="workout-chat-title">Workout</span>
          {showRest && <span className="rest-indicator">Resting</span>}
        </div>
        <div className="messages" ref={messagesRef}>
          {messages.length === 0 && (
            <div className="messages-empty">
              <p className="messages-empty-text">
                Tell Claude what you're working on. It has your full training plan and history.
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <ChatBubble key={i} role={m.role} content={m.content} setCard={m.setCard}
              onSetStart={m.setCard ? () => handleSetStart(m.setCard!) : undefined} />
          ))}
          {showRest && (
            <RestTimer seconds={REST_DURATION} onComplete={() => setShowRest(false)} />
          )}
          {thinking && (
            <div className="chat-bubble assistant typing">
              <span className="claude-label">CLAUDE</span>
              <span className="typing-dots"><span /><span /><span /></span>
            </div>
          )}
        </div>
        <div className="input-bar">
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send(input)}
            placeholder="Tell Claude how that set felt..." />
          <button className="send-btn" onClick={() => send(input)}>{'\u2191'}</button>
        </div>
      </div>
    )
  }

  // state A: daily chat (default)
  return (
    <div className="coach-screen">
      <div className="workout-chat-header">
        <button className="end-workout-btn" onClick={() => setShowDayList(true)}>
          {'\u2190'} Days
        </button>
        <span className="workout-chat-title">{formatDateHeader(chatDate)}</span>
      </div>
      <div className="messages" ref={messagesRef}>
        <ContextBanner date={chatDate} />
        {messages.length === 0 && (
          <div className="messages-empty">
            <p className="messages-empty-text">
              Chat with Claude about training, nutrition, or anything else.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <ChatBubble key={i} role={m.role} content={m.content} setCard={m.setCard}
            onSetStart={m.setCard ? () => handleSetStart(m.setCard!) : undefined} />
        ))}
        {thinking && (
          <div className="chat-bubble assistant typing">
            <span className="claude-label">CLAUDE</span>
            <span className="typing-dots"><span /><span /><span /></span>
          </div>
        )}
      </div>
      <div className="input-bar">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send(input)}
          placeholder="Ask Claude anything..." />
        <button className="send-btn" onClick={() => send(input)}>{'\u2191'}</button>
      </div>
    </div>
  )
}
