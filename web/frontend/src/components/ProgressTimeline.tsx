import { useEffect, useRef } from 'react'
import type { ProgressEvent } from '../types'

const TOOL_COLORS: Record<string, string> = {
  Read: 'bg-sky-100 text-sky-700',
  Write: 'bg-emerald-100 text-emerald-700',
  Edit: 'bg-amber-100 text-amber-700',
  Glob: 'bg-purple-100 text-purple-700',
  Grep: 'bg-purple-100 text-purple-700',
  Bash: 'bg-slate-200 text-slate-700',
  Task: 'bg-blue-100 text-blue-700',
  SendMessage: 'bg-indigo-100 text-indigo-700',
  TeamCreate: 'bg-pink-100 text-pink-700',
  TeamDelete: 'bg-pink-100 text-pink-700',
  TaskCreate: 'bg-orange-100 text-orange-700',
  TaskUpdate: 'bg-orange-100 text-orange-700',
  TaskList: 'bg-orange-100 text-orange-700',
  TaskGet: 'bg-orange-100 text-orange-700',
}

function ToolBadge({ name }: { name: string }) {
  const color = TOOL_COLORS[name] || 'bg-slate-100 text-slate-600'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono font-medium ${color}`}>
      {name}
    </span>
  )
}

function formatTime(ts?: string): string {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDuration(ms?: number): string {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${s}s`
}

export default function ProgressTimeline({
  events,
  isRunning,
}: {
  events: ProgressEvent[]
  isRunning: boolean
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [events])

  return (
    <div className="rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="bg-slate-800 px-4 py-2 flex items-center justify-between border-b border-slate-700">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-xs text-slate-400 ml-2 font-mono">progress</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 font-mono">{events.length} steps</span>
          {isRunning && (
            <span className="flex items-center gap-1.5 text-xs text-blue-400">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              live
            </span>
          )}
        </div>
      </div>
      {/* Body */}
      <div
        ref={containerRef}
        className="bg-slate-900 p-4 overflow-auto max-h-[500px] scrollbar-dark"
      >
        {events.length === 0 ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            {isRunning ? (
              <>
                <svg className="w-4 h-4 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Waiting for progress...
              </>
            ) : (
              <span className="text-slate-600">No progress events</span>
            )}
          </div>
        ) : (
          <div className="space-y-1">
            {events.map((ev, i) => (
              <ProgressRow key={i} event={ev} index={i} />
            ))}
            {isRunning && (
              <div className="flex items-center gap-2 pl-8 pt-1 text-slate-500 text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                Processing...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ProgressRow({ event: ev, index }: { event: ProgressEvent; index: number }) {
  if (ev.event === 'tool_use') {
    return (
      <div className="flex items-start gap-2 py-0.5 group hover:bg-slate-800/50 rounded px-1 -mx-1">
        <span className="text-slate-600 text-[11px] font-mono w-6 text-right flex-shrink-0 pt-0.5 select-none">
          {index + 1}
        </span>
        <span className="text-slate-500 pt-0.5 flex-shrink-0">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </span>
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <ToolBadge name={ev.tool || ''} />
          <span className="text-slate-400 text-xs font-mono truncate">{ev.detail}</span>
        </div>
        <span className="text-slate-600 text-[10px] font-mono flex-shrink-0 opacity-0 group-hover:opacity-100">
          {formatTime(ev.timestamp)}
        </span>
      </div>
    )
  }

  if (ev.event === 'text') {
    return (
      <div className="flex items-start gap-2 py-0.5 group hover:bg-slate-800/50 rounded px-1 -mx-1">
        <span className="text-slate-600 text-[11px] font-mono w-6 text-right flex-shrink-0 pt-0.5 select-none">
          {index + 1}
        </span>
        <span className="text-slate-500 pt-0.5 flex-shrink-0">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        </span>
        <span className="text-slate-300 text-xs leading-relaxed break-words min-w-0">{ev.detail}</span>
        <span className="text-slate-600 text-[10px] font-mono flex-shrink-0 opacity-0 group-hover:opacity-100">
          {formatTime(ev.timestamp)}
        </span>
      </div>
    )
  }

  if (ev.event === 'result') {
    const isSuccess = ev.subtype === 'success'
    return (
      <div className={`flex items-start gap-2 py-1.5 px-2 -mx-1 rounded mt-1 ${isSuccess ? 'bg-emerald-950/30' : 'bg-red-950/30'}`}>
        <span className="text-slate-600 text-[11px] font-mono w-6 text-right flex-shrink-0 pt-0.5 select-none">
          {index + 1}
        </span>
        <span className={`pt-0.5 flex-shrink-0 ${isSuccess ? 'text-emerald-400' : 'text-red-400'}`}>
          {isSuccess ? (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
        </span>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-medium ${isSuccess ? 'text-emerald-400' : 'text-red-400'}`}>
            {isSuccess ? 'Completed' : 'Failed'}
          </span>
          {ev.duration_ms && (
            <span className="text-xs text-slate-500">{formatDuration(ev.duration_ms)}</span>
          )}
          {ev.num_turns && (
            <span className="text-xs text-slate-500">{ev.num_turns} turns</span>
          )}
          {ev.cost_usd != null && (
            <span className="text-xs text-slate-500">${ev.cost_usd.toFixed(3)}</span>
          )}
        </div>
      </div>
    )
  }

  return null
}
