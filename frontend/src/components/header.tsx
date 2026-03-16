export function Header({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="header">
      <h1>{title}</h1>
      {subtitle && <p className="subtitle">{subtitle}</p>}
    </div>
  )
}
