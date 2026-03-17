import { useState, useRef } from 'react'

interface OnboardingProps {
  onComplete: () => void
}

interface Slide {
  key: string
  render: (onComplete?: () => void) => React.ReactNode
}

const slides: Slide[] = [
  {
    key: 'welcome',
    render: () => (
      <>
        <span className="onboarding-emoji">{'\uD83D\uDCAA'}</span>
        <h1>SpotMe</h1>
        <h2>Your AI Training Partner</h2>
        <p>An AI coach that learns how you train, adapts to your body, and gets smarter every session.</p>
      </>
    ),
  },
  {
    key: 'how-it-works',
    render: () => (
      <>
        <span className="onboarding-label">HOW IT WORKS</span>
        <h2>Just talk to Claude</h2>
        <div className="onboarding-chat-examples">
          <div className="onboarding-bubble user">"225 for 5, felt easy"</div>
          <div className="onboarding-bubble assistant">"Bumping to 235 next set. You've got 3 more reps in you."</div>
          <div className="onboarding-bubble user">"What should I do for accessories?"</div>
          <div className="onboarding-bubble assistant">"Based on your program, try RDLs 3x10 then leg curls."</div>
        </div>
      </>
    ),
  },
  {
    key: 'learns',
    render: () => (
      <>
        <span className="onboarding-label">GETS SMARTER</span>
        <h2>Every session makes it better</h2>
        <div className="onboarding-features">
          <div className="onboarding-feature-card">
            <strong>Adapts weights</strong>
            <p>Adjusts suggestions based on your RPE and progression</p>
          </div>
          <div className="onboarding-feature-card">
            <strong>Reads recovery</strong>
            <p>Uses Whoop HRV and sleep to calibrate intensity</p>
          </div>
          <div className="onboarding-feature-card">
            <strong>Remembers preferences</strong>
            <p>Learns your exercise selection, rest times, and style</p>
          </div>
        </div>
      </>
    ),
  },
  {
    key: 'tips',
    render: () => (
      <>
        <span className="onboarding-label">PRO TIPS</span>
        <h2>Quick Tips</h2>
        <ol className="onboarding-tips">
          <li><strong>Say how it felt</strong> — RPE helps Claude dial in your weights</li>
          <li><strong>Ask anything</strong> — form cues, substitutions, program changes</li>
          <li><strong>Override anytime</strong> — Claude suggests, you decide</li>
          <li><strong>Check the top bar</strong> — see your workout progress at a glance</li>
        </ol>
      </>
    ),
  },
  {
    key: 'start',
    render: (onComplete?: () => void) => (
      <>
        <span className="onboarding-emoji">{'\uD83C\uDFC6'}</span>
        <h2>Ready to train</h2>
        <p>Start by telling Claude what you want to work on, or let it suggest based on your program.</p>
        <button className="onboarding-cta" onClick={onComplete}>
          Start Training
        </button>
      </>
    ),
  },
]

const SWIPE_THRESHOLD = 50

export function Onboarding({ onComplete }: OnboardingProps) {
  const [currentSlide, setCurrentSlide] = useState(0)
  const touchStartX = useRef(0)

  const handleComplete = () => {
    localStorage.setItem('spotme_onboarded', '1')
    onComplete()
  }

  const goTo = (index: number) => {
    if (index >= 0 && index < slides.length) {
      setCurrentSlide(index)
    }
  }

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX
  }

  const handleTouchEnd = (e: React.TouchEvent) => {
    const delta = touchStartX.current - e.changedTouches[0].clientX
    if (Math.abs(delta) > SWIPE_THRESHOLD) {
      if (delta > 0) {
        goTo(currentSlide + 1)
      } else {
        goTo(currentSlide - 1)
      }
    }
  }

  return (
    <div
      className="onboarding"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      <div
        className="onboarding-track"
        style={{ transform: `translateX(-${currentSlide * 100}vw)` }}
      >
        {slides.map((slide) => (
          <div key={slide.key} className="onboarding-slide">
            {slide.render(slide.key === 'start' ? handleComplete : undefined)}
          </div>
        ))}
      </div>
      <div className="onboarding-dots">
        {slides.map((slide, i) => (
          <span
            key={slide.key}
            className={`onboarding-dot${i === currentSlide ? ' active' : ''}`}
            onClick={() => goTo(i)}
          />
        ))}
      </div>
    </div>
  )
}
