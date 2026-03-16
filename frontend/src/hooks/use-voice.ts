import { useState, useCallback, useRef } from 'react'

export function useVoice() {
  const [transcript, setTranscript] = useState('')
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<any>(null)
  const start = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) return
    const recognition = new SR()
    recognition.continuous = false; recognition.interimResults = false; recognition.lang = 'en-US'
    recognition.onresult = (event: any) => { setTranscript(event.results[0][0].transcript); setListening(false) }
    recognition.onerror = () => setListening(false)
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition; recognition.start(); setListening(true)
  }, [])
  const stop = useCallback(() => { recognitionRef.current?.stop(); setListening(false) }, [])
  return { transcript, listening, start, stop }
}
