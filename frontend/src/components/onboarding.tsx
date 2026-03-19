import { useState } from 'react'
import { api } from '../api'

function userKey(key: string): string {
  const match = window.location.pathname.match(/^\/u\/([a-zA-Z0-9_-]+)/)
  const prefix = match ? `spotme_${match[1]}` : 'spotme'
  return `${prefix}_${key}`
}

interface OnboardingProps {
  onComplete: () => void
}

type Step = 'welcome' | 'profile' | 'whoop' | 'generating'

export function Onboarding({ onComplete }: OnboardingProps) {
  const [step, setStep] = useState<Step>('welcome')
  const [name, setName] = useState('')
  const [experience, setExperience] = useState('')
  const [goals, setGoals] = useState('')
  const [frequency, setFrequency] = useState('')
  const [equipment, setEquipment] = useState('')
  const [showEquipment, setShowEquipment] = useState(false)
  const [whoopEmail, setWhoopEmail] = useState('')
  const [whoopPassword, setWhoopPassword] = useState('')
  const [whoopStatus, setWhoopStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle')
  const [whoopError, setWhoopError] = useState('')
  const [generatingStatus, setGeneratingStatus] = useState('')

  const experienceOptions = ['Beginner', 'Intermediate', 'Advanced']
  const goalOptions = ['Strength', 'Hypertrophy', 'Conditioning', 'General fitness']
  const freqOptions = ['2x/week', '3x/week', '4x/week', '5x/week', '6x/week']

  const canSubmitProfile = name.trim() && experience && goals && frequency

  const connectWhoop = async () => {
    setWhoopStatus('connecting')
    setWhoopError('')
    try {
      const result = await api.whoopLogin(whoopEmail, whoopPassword)
      if (result.connected || result.success) {
        setWhoopStatus('connected')
      } else {
        setWhoopStatus('error')
        setWhoopError(result.error || 'Connection failed')
      }
    } catch {
      setWhoopStatus('error')
      setWhoopError('Could not connect. Check your credentials.')
    }
  }

  const finishOnboarding = async () => {
    setStep('generating')
    setGeneratingStatus('Building your training program...')
    try {
      await api.intake({
        name,
        experience_level: experience,
        goals,
        equipment: equipment || 'Full gym',
        training_frequency: frequency,
      })
      localStorage.setItem(userKey('onboarded'), '1')
      localStorage.setItem(userKey('intake_done'), '1')
      onComplete()
    } catch {
      setGeneratingStatus('Something went wrong. Trying again...')
      setTimeout(() => finishOnboarding(), 2000)
    }
  }

  return (
    <div className="onboarding">
      {step === 'welcome' && (
        <div className="onboarding-slide">
          <span className="onboarding-emoji">{'\uD83D\uDCAA'}</span>
          <h1>SpotMe</h1>
          <h2>Your AI Training Partner</h2>
          <p>An AI coach that learns how you train, adapts to your recovery, and gets smarter every session.</p>
          <input
            className="onboarding-name-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Your name"
            autoFocus
            onKeyDown={e => e.key === 'Enter' && name.trim() && setStep('profile')}
          />
          <button
            className="onboarding-cta"
            disabled={!name.trim()}
            onClick={() => setStep('profile')}
          >
            Get Started
          </button>
        </div>
      )}

      {step === 'profile' && (
        <div className="onboarding-slide">
          <h2>Quick setup</h2>
          <p>Tell Claude about yourself so it can build your program.</p>

          <div className="onboarding-section">
            <label>Experience</label>
            <div className="intake-options">
              {experienceOptions.map(opt => (
                <button
                  key={opt}
                  className={`intake-option${experience === opt.toLowerCase() ? ' selected' : ''}`}
                  onClick={() => setExperience(opt.toLowerCase())}
                >{opt}</button>
              ))}
            </div>
          </div>

          <div className="onboarding-section">
            <label>Goal</label>
            <div className="intake-options">
              {goalOptions.map(opt => (
                <button
                  key={opt}
                  className={`intake-option${goals === opt.toLowerCase() ? ' selected' : ''}`}
                  onClick={() => setGoals(opt.toLowerCase())}
                >{opt}</button>
              ))}
            </div>
          </div>

          <div className="onboarding-section">
            <label>Training days</label>
            <div className="intake-options">
              {freqOptions.map(opt => (
                <button
                  key={opt}
                  className={`intake-option${frequency === opt ? ' selected' : ''}`}
                  onClick={() => setFrequency(opt)}
                >{opt}</button>
              ))}
            </div>
          </div>

          {!showEquipment ? (
            <button className="onboarding-link" onClick={() => setShowEquipment(true)}>
              + Add equipment details
            </button>
          ) : (
            <div className="onboarding-section">
              <label>Equipment</label>
              <textarea
                className="intake-textarea"
                value={equipment}
                onChange={e => setEquipment(e.target.value)}
                placeholder="e.g., Full gym, dumbbells only, home setup..."
                rows={2}
              />
            </div>
          )}

          <button
            className="onboarding-cta"
            disabled={!canSubmitProfile}
            onClick={() => setStep('whoop')}
          >
            Next
          </button>
        </div>
      )}

      {step === 'whoop' && (
        <div className="onboarding-slide">
          <h2>Connect Whoop</h2>
          <p>Optional — lets Claude read your recovery and auto-sync workouts.</p>

          {whoopStatus === 'connected' ? (
            <div className="onboarding-whoop-connected">
              <span className="onboarding-check">{'\u2713'}</span>
              <p>Whoop connected! Claude can now see your recovery data.</p>
              <button className="onboarding-cta" onClick={finishOnboarding}>
                Build My Program
              </button>
            </div>
          ) : (
            <>
              <input
                className="onboarding-name-input"
                type="email"
                value={whoopEmail}
                onChange={e => setWhoopEmail(e.target.value)}
                placeholder="Whoop email"
              />
              <input
                className="onboarding-name-input"
                type="password"
                value={whoopPassword}
                onChange={e => setWhoopPassword(e.target.value)}
                placeholder="Whoop password"
                onKeyDown={e => e.key === 'Enter' && whoopEmail && whoopPassword && connectWhoop()}
              />
              {whoopError && <p className="onboarding-error">{whoopError}</p>}
              <button
                className="onboarding-cta"
                disabled={whoopStatus === 'connecting' || (!whoopEmail || !whoopPassword)}
                onClick={connectWhoop}
              >
                {whoopStatus === 'connecting' ? 'Connecting...' : 'Connect'}
              </button>
              <button className="onboarding-skip" onClick={finishOnboarding}>
                Skip — I don't have a Whoop
              </button>
            </>
          )}
        </div>
      )}

      {step === 'generating' && (
        <div className="onboarding-slide">
          <div className="onboarding-spinner" />
          <h2>Setting up your coach</h2>
          <p>{generatingStatus}</p>
        </div>
      )}
    </div>
  )
}
