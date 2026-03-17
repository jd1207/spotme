import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { ChatBubble } from '../components/chat-bubble'
import { RestTimer } from '../components/rest-timer'
import { WorkoutHome } from './workout-home'
import type { Message, SetSuggestion } from '../types'

const REST_DURATION = 120

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

export function Workout() {
  const [activeWorkoutId, setActiveWorkoutId] = useState<number | null>(null)
  const [viewOnly, setViewOnly] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [showRest, setShowRest] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages, thinking, showRest])

  const startWorkout = async () => {
    try {
      const result = await api.startWorkout()
      setActiveWorkoutId(result.id)
      setViewOnly(false)
      if (result.resumed) {
        const history = await api.getChatHistory(result.id)
        setMessages(history.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })))
      }
    } catch {
      // offline fallback
    }
  }

  const startGeneralChat = () => {
    setActiveWorkoutId(-1)
    setViewOnly(false)
    setMessages([])
  }

  const endWorkout = async () => {
    if (activeWorkoutId && activeWorkoutId > 0 && !viewOnly) {
      try {
        await api.completeWorkout(activeWorkoutId)
      } catch {}
    }
    setActiveWorkoutId(null)
    setViewOnly(false)
    setMessages([])
  }

  const viewPastWorkout = async (workoutId: number) => {
    try {
      const history = await api.getChatHistory(workoutId)
      setMessages(history.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })))
      setActiveWorkoutId(workoutId)
      setViewOnly(true)
    } catch {}
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
      const result = await api.chat(text, wid)
      const msg: Message = { role: 'assistant', content: result.response }
      // prefer structured set_suggestion from api, fall back to regex
      const structured = result.set_suggestion
      msg.setCard = structured
        ? { exercise: structured.exercise, weight: structured.weight, reps: structured.reps, basis: structured.basis || 'Claude suggestion' }
        : extractSetFromText(result.response)
      // fetch previous performance for this exercise
      if (msg.setCard) {
        try {
          const lastData = await api.getLastExercise(msg.setCard.exercise)
          if (lastData.sets.length > 0) {
            msg.setCard.lastSet = lastData.sets[0]
          }
        } catch { /* ignore — last set is a nice-to-have */ }
      }
      setMessages(m => [...m, msg])
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Connection error — try again in a sec.' }])
    } finally {
      setThinking(false)
    }
  }

  if (!activeWorkoutId) {
    return <WorkoutHome onStartWorkout={startWorkout} onStartChat={startGeneralChat} onViewPast={viewPastWorkout} />
  }

  return (
    <div className="coach-screen">
      <div className="workout-chat-header">
        <button className="end-workout-btn" onClick={endWorkout}>{viewOnly ? 'Back' : activeWorkoutId === -1 ? 'Close' : 'End'}</button>
        <span className="workout-chat-title">{viewOnly ? 'Past Workout' : activeWorkoutId === -1 ? 'Chat' : 'Workout'}</span>
        {showRest && !viewOnly && <span className="rest-indicator">Resting</span>}
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
          <ChatBubble key={i} role={m.role} content={m.content} setCard={m.setCard} onSetStart={m.setCard ? () => handleSetStart(m.setCard!) : undefined} />
        ))}
        {showRest && !viewOnly && (
          <RestTimer seconds={REST_DURATION} onComplete={() => setShowRest(false)} />
        )}
        {thinking && (
          <div className="chat-bubble assistant typing">
            <span className="claude-label">CLAUDE</span>
            <span className="typing-dots"><span /><span /><span /></span>
          </div>
        )}
      </div>
      {!viewOnly && (
        <div className="input-bar">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send(input)}
            placeholder="Tell Claude how that set felt..."
          />
          <button className="send-btn" onClick={() => send(input)}>{'\u2191'}</button>
        </div>
      )}
    </div>
  )
}
