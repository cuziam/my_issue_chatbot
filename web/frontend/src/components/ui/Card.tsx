import { useState } from 'react'

interface CardProps {
  title?: string
  subtitle?: string
  collapsible?: boolean
  defaultOpen?: boolean
  padding?: boolean
  className?: string
  children: React.ReactNode
}

export default function Card({
  title,
  subtitle,
  collapsible = false,
  defaultOpen = true,
  padding = true,
  className = '',
  children,
}: CardProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className={`bg-white rounded-xl border border-slate-200 ${className}`}>
      {title && (
        <div
          className={`px-4 py-3 ${collapsible ? 'cursor-pointer select-none hover:bg-slate-50' : ''} ${open && children ? 'border-b border-slate-100' : ''}`}
          onClick={collapsible ? () => setOpen(!open) : undefined}
        >
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</h3>
              {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
            </div>
            {collapsible && (
              <svg
                className={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            )}
          </div>
        </div>
      )}
      {(!collapsible || open) && (
        <div className={padding ? 'p-4' : ''}>
          {children}
        </div>
      )}
    </div>
  )
}
