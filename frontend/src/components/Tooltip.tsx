import { useState, type ReactNode } from 'react'

interface Props {
  text: string
  children: ReactNode
}

export default function Tooltip({ text, children }: Props) {
  const [show, setShow] = useState(false)

  return (
    <span
      className="relative cursor-help"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onClick={() => setShow(!show)}
    >
      {children}
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-terminal-surface border border-terminal-border rounded text-xs text-terminal-text whitespace-nowrap shadow-lg">
          {text}
        </span>
      )}
    </span>
  )
}
