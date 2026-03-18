import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { ChatBubble } from '../components/chat-bubble'
import { SetCard } from '../components/set-card'
import { ContextBanner } from '../components/context-banner'
import { DayList } from './workout-home'
import type { Message, PlannedSet, SetProgress } from '../types'

function todayEastern(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}

function formatDateHeader(date: string): string {
  if (date === todayEastern()) return 'Today'
  const d = new Date(date + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

export function Workout() {
  const [workoutId, setWorkoutId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [chatDate, setChatDate] = useState(todayEastern)
  const [showDayList, setShowDayList] = useState(false)
  const [currentSet, setCurrentSet] = useState<PlannedSet | null>(null)
  const [setProgress, setSetProgress] = useState<SetProgress | null>(null)
  const [nextPreview, setNextPreview] = useState<string | null>(null)
  const messagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // use setTimeout to scroll after DOM updates
    setTimeout(() => {
      if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }, 50)
  }, [messages, thinking])

  useEffect(() => {
    if (workoutId) return
    api.getChatDay(chatDate)
      .then(r => setMessages(r.messages.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content }))))
      .catch(() => setMessages([]))
  }, [chatDate, workoutId])

  const endWorkout = async () => {
    if (workoutId && workoutId > 0) {
      try { await api.completeWorkout(workoutId) } catch {}
    }
    setWorkoutId(null)
    setCurrentSet(null)
    setSetProgress(null)
    setNextPreview(null)
    setChatDate(todayEastern())
    setMessages([])
  }

  const applySetResult = (result: import('../types').CompleteSetResponse) => {
    if (result.next_set) {
      setCurrentSet(result.next_set)
      setSetProgress(result.progress)
      setNextPreview(result.next_exercise_preview)
    } else {
      setCurrentSet(null)
      setMessages(m => [...m, { role: 'assistant', content: 'Workout complete! Great session.' }])
    }
  }

  const handleSetComplete = async (weight: number, reps: number, feel: string | null) => {
    if (!currentSet) return
    try {
      applySetResult(await api.completeSet({
        set_id: currentSet.id, actual_weight: weight, actual_reps: reps, feel: feel ?? undefined,
      }))
    } catch { /* set card stays on current set */ }
  }

  const handleSetSkip = async () => {
    if (!currentSet) return
    try {
      applySetResult(await api.completeSet({
        set_id: currentSet.id, actual_weight: 0, actual_reps: 0, feel: undefined,
      }))
    } catch {}
  }

  const send = async (text: string) => {
    if (!text.trim()) return
    setMessages(m => [...m, { role: 'user', content: text }])
    setInput('')
    setThinking(true)
    try {
      const wid = workoutId && workoutId > 0 ? workoutId : undefined
      const result = await api.chat(text, wid, wid ? undefined : chatDate)
      setMessages(m => [...m, { role: 'assistant', content: result.response }])
      if (result.workout_active && result.current_set) {
        setWorkoutId(result.workout_id ?? null)
        setCurrentSet(result.current_set)
        setSetProgress({ completed: 0, total: 0, current_exercise_progress: '0 of 0' })
      }
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Connection error — try again in a sec.' }])
    } finally {
      setThinking(false)
    }
  }

  // state B: day list
  if (!workoutId && showDayList) {
    return <DayList onSelectDay={(date: string) => { setChatDate(date); setShowDayList(false) }} />
  }

  const thinkingIndicator = thinking && (
    <div className="chat-bubble assistant typing">
      <span className="claude-label">CLAUDE</span>
      <span className="typing-dots"><span /><span /><span /></span>
    </div>
  )

  const inputBar = (placeholder: string) => (
    <div className="input-bar">
      <input value={input} onChange={e => setInput(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && send(input)} placeholder={placeholder} />
      <button className="send-btn" onClick={() => send(input)}>{'\u2191'}</button>
    </div>
  )

  // state C: active workout with sticky set card
  if (workoutId) {
    return (
      <div className="coach-screen">
        <div className="workout-chat-header">
          <button className="end-workout-btn" onClick={endWorkout}>End</button>
          <span className="workout-chat-title">Workout</span>
        </div>
        <div className="messages" ref={messagesRef}>
          {messages.length === 0 && (
            <div className="messages-empty">
              <p className="messages-empty-text">Tell Claude what you're working on. It has your full training plan and history.</p>
            </div>
          )}
          {messages.map((m, i) => <ChatBubble key={i} role={m.role} content={m.content} />)}
          {thinkingIndicator}
        </div>
        {currentSet && setProgress && (
          <SetCard currentSet={currentSet} progress={setProgress} nextPreview={nextPreview}
            onComplete={handleSetComplete} onSkip={handleSetSkip} />
        )}
        {inputBar('Tell Claude how that set felt...')}
      </div>
    )
  }

  // state A: daily chat (default)
  return (
    <div className="coach-screen">
      <div className="workout-chat-header">
        <button className="end-workout-btn" onClick={() => setShowDayList(true)}>{'\u2190'} Days</button>
        <span className="workout-chat-title">{formatDateHeader(chatDate)}</span>
      </div>
      <div className="messages" ref={messagesRef}>
        <ContextBanner date={chatDate} />
        {messages.length === 0 && (
          <div className="messages-empty">
            <p className="messages-empty-text">Chat with Claude about training, nutrition, or anything else.</p>
          </div>
        )}
        {messages.map((m, i) => <ChatBubble key={i} role={m.role} content={m.content} />)}
        {thinkingIndicator}
      </div>
      {inputBar('Ask Claude anything...')}
    </div>
  )
}
