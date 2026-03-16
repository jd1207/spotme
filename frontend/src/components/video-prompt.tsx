export function VideoPrompt({ message, onCapture }: { message: string; onCapture?: () => void }) {
  return (
    <div className="video-prompt">
      <p>{message}</p>
      <button className="camera-btn" onClick={onCapture}>Record</button>
    </div>
  )
}
