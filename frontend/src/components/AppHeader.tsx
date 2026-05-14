import { NavLink } from 'react-router-dom'

export default function AppHeader() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1 rounded text-sm transition-colors ${
      isActive
        ? 'bg-terminal-green/20 text-terminal-green'
        : 'text-terminal-muted hover:text-terminal-text'
    }`

  return (
    <header className="border-b border-terminal-border bg-terminal-surface px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-terminal-green font-bold text-lg">$</span>
        <h1 className="text-base font-bold tracking-tight">OptionTerminal</h1>
      </div>

      <nav className="flex items-center gap-2">
        <NavLink to="/" className={linkClass} end>
          Screener
        </NavLink>
        <NavLink to="/report" className={linkClass}>
          Report
        </NavLink>
      </nav>
    </header>
  )
}
