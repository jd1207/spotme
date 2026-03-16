export function ActionButton({ label, onClick }: { label: string; onClick?: () => void }) {
  return <button className="action-button" onClick={onClick}>{label}</button>
}
