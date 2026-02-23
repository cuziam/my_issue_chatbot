import { useEffect, useRef } from 'react'

export default function AnalysisLog({ lines }: { lines: string[] }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines])

  return (
    <div className="rounded-xl border border-slate-700 overflow-hidden">
      {/* Terminal header */}
      <div className="bg-slate-800 px-4 py-2 flex items-center justify-between border-b border-slate-700">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-xs text-slate-400 ml-2 font-mono">output</span>
        </div>
        <span className="text-xs text-slate-500 font-mono">{lines.length} lines</span>
      </div>
      {/* Terminal body */}
      <div
        ref={containerRef}
        className="bg-slate-900 text-slate-300 font-mono text-[0.8rem] leading-relaxed p-4 overflow-auto max-h-[500px] scrollbar-dark"
      >
        {lines.length === 0 ? (
          <div className="flex items-center gap-2 text-slate-500">
            <svg className="w-4 h-4 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Waiting for output...
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="flex gap-3 hover:bg-slate-800/50">
              <span className="text-slate-600 select-none w-8 text-right flex-shrink-0">{i + 1}</span>
              <span className="whitespace-pre-wrap break-all">{line}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
