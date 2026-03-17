import { useState } from 'react'
import { api } from '../api'

interface IntakeProps {
  onComplete: () => void
}

const STEPS = ['name', 'experience', 'goals', 'equipment', 'frequency', 'plan'] as const
type Step = typeof STEPS[number]

const EXPERIENCE_OPTIONS = ['Beginner', 'Intermediate', 'Advanced']
const GOAL_OPTIONS = ['Strength', 'Hypertrophy', 'Conditioning', 'Sport-specific']
const FREQ_OPTIONS = ['2x/week', '3x/week', '4x/week', '5x/week', '6x/week']

export function Intake({ onComplete }: IntakeProps) {
  const [step, setStep] = useState<Step>('name')
  const [name, setName] = useState('')
  const [experience, setExperience] = useState('')
  const [goals, setGoals] = useState('')
  const [equipment, setEquipment] = useState('')
  const [frequency, setFrequency] = useState('')
  const [plan, setPlan] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [status, setStatus] = useState('')

  const stepIndex = STEPS.indexOf(step)
  const isLast = step === 'plan'

  const canProceed = () => {
    if (step === 'name') return name.trim().length > 0
    if (step === 'experience') return experience.length > 0
    if (step === 'goals') return goals.length > 0
    if (step === 'equipment') return equipment.trim().length > 0
    if (step === 'frequency') return frequency.length > 0
    return true
  }

  const next = () => {
    if (!isLast && canProceed()) {
      setStep(STEPS[stepIndex + 1])
    }
  }

  const submit = async () => {
    setSubmitting(true)
    setStatus('Setting up your coach...')
    try {
      await api.intake({
        name, experience_level: experience, goals, equipment,
        training_frequency: frequency, training_plan: plan,
      })
      localStorage.setItem('spotme_intake_done', '1')
      setStatus('')
      onComplete()
    } catch {
      setStatus('Something went wrong. Try again.')
      setSubmitting(false)
    }
  }

  return (
    <div className="intake">
      <div className="intake-progress">
        {STEPS.map((s, i) => (
          <span key={s} className={`intake-dot${i <= stepIndex ? ' filled' : ''}`} />
        ))}
      </div>

      <div className="intake-content">
        {step === 'name' && (
          <>
            <h2>What's your name?</h2>
            <p>Claude will use this to personalize your coaching.</p>
            <input
              className="intake-input"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Your name"
              autoFocus
              onKeyDown={e => e.key === 'Enter' && next()}
            />
          </>
        )}

        {step === 'experience' && (
          <>
            <h2>Training experience?</h2>
            <p>This helps Claude calibrate intensity and coaching style.</p>
            <div className="intake-options">
              {EXPERIENCE_OPTIONS.map(opt => (
                <button key={opt} className={`intake-option${experience === opt.toLowerCase() ? ' selected' : ''}`}
                  onClick={() => setExperience(opt.toLowerCase())}>{opt}</button>
              ))}
            </div>
          </>
        )}

        {step === 'goals' && (
          <>
            <h2>Primary goal?</h2>
            <p>What are you training for?</p>
            <div className="intake-options">
              {GOAL_OPTIONS.map(opt => (
                <button key={opt} className={`intake-option${goals === opt.toLowerCase() ? ' selected' : ''}`}
                  onClick={() => setGoals(opt.toLowerCase())}>{opt}</button>
              ))}
            </div>
          </>
        )}

        {step === 'equipment' && (
          <>
            <h2>Equipment available?</h2>
            <p>What do you have access to?</p>
            <textarea
              className="intake-textarea"
              value={equipment}
              onChange={e => setEquipment(e.target.value)}
              placeholder="e.g., Bench, dumbbells, cable machine, Smith machine..."
              rows={3}
            />
          </>
        )}

        {step === 'frequency' && (
          <>
            <h2>How often do you train?</h2>
            <p>Days per week you can commit to.</p>
            <div className="intake-options">
              {FREQ_OPTIONS.map(opt => (
                <button key={opt} className={`intake-option${frequency === opt ? ' selected' : ''}`}
                  onClick={() => setFrequency(opt)}>{opt}</button>
              ))}
            </div>
          </>
        )}

        {step === 'plan' && (
          <>
            <h2>Got a training plan?</h2>
            <p>Paste your program, training export, or notes below. Claude will parse it and build your workout schedule. Or leave blank and Claude will create one.</p>
            <textarea
              className="intake-textarea tall"
              value={plan}
              onChange={e => setPlan(e.target.value)}
              placeholder="Paste your training plan here (optional)..."
              rows={8}
            />
          </>
        )}
      </div>

      <div className="intake-actions">
        {stepIndex > 0 && !submitting && (
          <button className="intake-back" onClick={() => setStep(STEPS[stepIndex - 1])}>Back</button>
        )}
        {status && <span className="intake-status">{status}</span>}
        {!isLast ? (
          <button className="intake-next" onClick={next} disabled={!canProceed()}>Next</button>
        ) : (
          <button className="intake-next" onClick={submit} disabled={submitting}>
            {submitting ? 'Setting up...' : plan.trim() ? 'Load Plan' : 'Start Training'}
          </button>
        )}
      </div>
    </div>
  )
}
