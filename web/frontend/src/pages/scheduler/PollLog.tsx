import type { PollLogEntry } from '../../types'

export interface PollLogProps {
  pollLog: PollLogEntry[]
}

export default function PollLog({ pollLog }: PollLogProps) {
  if (pollLog.length === 0) return null

  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <p className="text-xs font-medium text-slate-500 mb-2">Recent Activity</p>
      <div className="space-y-1 max-h-[120px] overflow-y-auto">
        {[...pollLog].reverse().slice(0, 10).map((entry, idx) => (
          <div key={idx} className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 w-16 shrink-0">
              {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            {entry.status === 'ok' ? (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            ) : (
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
            )}
            <span className="text-slate-600">
              {entry.status === 'ok'
                ? `${entry.trigger_count ?? 0} trigger(s)${entry.started_jobs_count ? `, ${entry.started_jobs_count} job(s) started` : ''}`
                : entry.error ?? 'Error'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
