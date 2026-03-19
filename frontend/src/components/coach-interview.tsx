import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

export interface InterviewMessage {
  role: 'coach' | 'user'
  content: string
}

interface CoachInterviewProps {
  profile: {
    name: string
    experience: string
    goals: string
    frequency: string
    equipment: string
  }
  onComplete: (messages: InterviewMessage[]) => void
}

export function CoachInterview({ profile, onComplete }: CoachInterviewProps) {
  const [questions, setQuestions] = useState<string[]>([])
  const [messages, setMessages] = useState<InterviewMessage[]>([])
  const [currentQ, setCurrentQ] = useState(0)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const messagesEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.interviewQuestions(profile)
      .then(result => {
        const qs = result.questions
        setQuestions(qs)
        setMessages([{ role: 'coach', content: qs[0] }])
        setLoading(false)
      })
      .catch(() => {
        const fallback = [
          "What are your current best lifts or recent PRs?",
          "Any injuries or limitations I should know about?",
          "What does your training week look like right now?",
          "Any specific numbers or goals you're chasing?",
        ]
        setQuestions(fallback)
        setMessages([{ role: 'coach', content: fallback[0] }])
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim()) return
    const answer = input.trim()
    setInput('')

    const nextQ = currentQ + 1
    const newMessages: InterviewMessage[] = [
      ...messages,
      { role: 'user', content: answer },
    ]

    if (nextQ < questions.length) {
      // add next question after a brief delay for natural feel
      setTimeout(() => {
        setMessages(prev => [...prev, { role: 'coach', content: questions[nextQ] }])
      }, 400)
    }

    setMessages(newMessages)
    setCurrentQ(nextQ)
  }

  const allAnswered = currentQ >= questions.length && questions.length > 0
  const answeredCount = messages.filter(m => m.role === 'user').length

  if (loading) {
    return (
      <div className="onboarding-slide">
        <div className="onboarding-spinner" />
        <h2>Getting to know you</h2>
        <p>Claude is reviewing your profile...</p>
      </div>
    )
  }

  return (
    <div className="coach-interview">
      <div className="coach-interview-header">
        <h2>Quick chat with your coach</h2>
        <span className="coach-interview-progress">
          {answeredCount} of {questions.length} answered
        </span>
      </div>

      <div className="coach-interview-messages">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`onboarding-bubble ${msg.role === 'coach' ? 'assistant' : 'user'}`}
          >
            {msg.content}
          </div>
        ))}
        <div ref={messagesEnd} />
      </div>

      {allAnswered ? (
        <div className="coach-interview-actions">
          <button className="onboarding-cta" onClick={() => onComplete(messages)}>
            Build My Program
          </button>
        </div>
      ) : (
        <div className="coach-interview-input">
          <input
            type="text"
            className="onboarding-name-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Type your answer..."
            autoFocus
            onKeyDown={e => e.key === 'Enter' && handleSend()}
          />
          <button
            className="coach-interview-send"
            disabled={!input.trim()}
            onClick={handleSend}
          >
            Send
          </button>
        </div>
      )}
    </div>
  )
}
