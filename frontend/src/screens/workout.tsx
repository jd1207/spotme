import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { ChatBubble } from '../components/chat-bubble'
import type { Message, SetSuggestion } from '../types'

const REST_DURATION = 120

export function Workout() {
  const [activeWorkoutId, setActiveWorkoutId] = useState<number | null>(null)
  const [viewOnly, setViewOnly] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [restSeconds, setRestSeconds] = useState(0)
  const [restActive, setRestActive] = useState(false)
  const [recentWorkouts, setRecentWorkouts] = useState<Array<{ id: number; date: string; type: string; status: string }>>([])
  const messagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.getRecentWorkouts().then(setRecentWorkouts).catch(() => {})
  }, [])

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages, thinking])

  useEffect(() => {
    if (!restActive) return
    const timer = setInterval(() => {
      setRestSeconds(s => {
        if (s <= 1) { setRestActive(false); return 0 }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [restActive])

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

  const endWorkout = async () => {
    if (activeWorkoutId && !viewOnly) {
      try {
        await api.completeWorkout(activeWorkoutId)
      } catch {}
    }
    setActiveWorkoutId(null)
    setViewOnly(false)
    setMessages([])
    api.getRecentWorkouts().then(setRecentWorkouts).catch(() => {})
  }

  const viewPastWorkout = async (workoutId: number) => {
    try {
      const history = await api.getChatHistory(workoutId)
      setMessages(history.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })))
      setActiveWorkoutId(workoutId)
      setViewOnly(true)
    } catch {}
  }

  const startRest = () => {
    setRestSeconds(REST_DURATION)
    setRestActive(true)
  }

  const handleSetStart = (suggestion: SetSuggestion) => {
    api.logSet({
      exercise_name: suggestion.exercise,
      weight: suggestion.weight,
      reps: suggestion.reps,
    }).catch(() => {})
    startRest()
  }

  const send = async (text: string) => {
    if (!text.trim()) return
    setMessages(m => [...m, { role: 'user', content: text }])
    setInput('')
    setThinking(true)
    try {
      const result = await api.chat(text, activeWorkoutId ?? undefined)
      const msg: Message = { role: 'assistant', content: result.response }
      // extract set suggestions from Claude's response (e.g., "try 235 x 5")
      const match = result.response.match(/(\d+)\s*(?:lbs?)?\s*[x\u00d7]\s*(\d+)/)
      if (match) {
        // try to extract exercise name from response context
        const exMatch = result.response.match(/(?:for|on|do)\s+([A-Z][a-z]+(?:\s+[A-Za-z]+){0,3})/i)
        msg.setCard = {
          exercise: exMatch ? exMatch[1] : 'Next Set',
          weight: parseInt(match[1]),
          reps: parseInt(match[2]),
          basis: 'Based on your feedback',
        }
      }
      setMessages(m => [...m, msg])
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Connection error — try again in a sec.' }])
    } finally {
      setThinking(false)
    }
  }

  // home screen — no active workout
  if (!activeWorkoutId) {
    return (
      <div className="workout-home">
        <div className="workout-home-header">
          <h2>Ready to train?</h2>
          <p>Start a workout session to chat with Claude about today's training.</p>
        </div>
        <button className="start-workout-btn" onClick={startWorkout}>Start Workout</button>

        {recentWorkouts.length > 0 && (
          <div className="recent-workouts">
            <h3 className="recent-title">Recent Sessions</h3>
            {recentWorkouts.map(w => (
              <button key={w.id} className={`recent-workout-card ${w.status}`} onClick={() => viewPastWorkout(w.id)}>
                <span className="recent-date">{w.date}</span>
                <span className="recent-type">{w.type}</span>
                <span className="recent-status">{w.status === 'active' ? 'In Progress' : 'Completed'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  // active workout — chat
  return (
    <div className="coach-screen">
      <div className="workout-chat-header">
        <button className="end-workout-btn" onClick={endWorkout}>{viewOnly ? 'Back' : 'End'}</button>
        <span className="workout-chat-title">{viewOnly ? 'Past Workout' : 'Workout'}</span>
        {restActive && !viewOnly && <span className="rest-indicator">{Math.floor(restSeconds / 60)}:{(restSeconds % 60).toString().padStart(2, '0')}</span>}
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
