import { useState, useRef, useCallback } from 'react'

export function useCamera() {
  const [recording, setRecording] = useState(false)
  const [videoBlob, setVideoBlob] = useState<Blob | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startRecording = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', height: { max: 1080 } }, audio: false })
    const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' })
    chunksRef.current = []
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
    recorder.onstop = () => { setVideoBlob(new Blob(chunksRef.current, { type: 'video/webm' })); stream.getTracks().forEach(t => t.stop()) }
    mediaRecorderRef.current = recorder; recorder.start(); setRecording(true)
    setTimeout(() => { if (recorder.state === 'recording') recorder.stop() }, 60000)
  }, [])
  const stopRecording = useCallback(() => { mediaRecorderRef.current?.stop(); setRecording(false) }, [])
  return { recording, videoBlob, startRecording, stopRecording }
}
