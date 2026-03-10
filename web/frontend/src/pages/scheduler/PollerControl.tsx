import type { PollerStatus, PollLogEntry } from '../../types'
import LoadingSpinner from '../../components/LoadingSpinner'
import PollLog from './PollLog'

export interface PollerControlProps {
  pollerStatus: PollerStatus | null
  pollerLoading: boolean
  intervalInput: number
  autoAnalyze: boolean
  pollNowLoading: boolean
  pollLog: PollLogEntry[]
  onTogglePoller: () => void
  onIntervalChange: (val: number) => void
  onAutoAnalyzeToggle: () => void
  onPollNow: () => void
  timeAgo: (iso: string | null) => string
  timeUntil: (iso: string | null) => string
}

export default function PollerControl({
  pollerStatus,
  pollerLoading,
  intervalInput,
  autoAnalyze,
  pollNowLoading,
  pollLog,
  onTogglePoller,
  onIntervalChange,
  onAutoAnalyzeToggle,
  onPollNow,
  timeAgo,
  timeUntil,
}: PollerControlProps) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center">
          <svg className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h2 className="text-sm font-semibold text-slate-800">Scheduler Poller</h2>
        {pollerStatus?.enabled && (
          <span className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Running
          </span>
        )}
      </div>

      {/* Controls Row */}
      <div className="flex items-center gap-4 flex-wrap">
        {/* Enable/Disable Toggle */}
        <button
          onClick={onTogglePoller}
          disabled={pollerLoading}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium shadow-sm transition-colors disabled:opacity-50 ${
            pollerStatus?.enabled
              ? 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'
              : 'bg-emerald-600 text-white hover:bg-emerald-700'
          }`}
        >
          {pollerLoading && <LoadingSpinner size="sm" />}
          {pollerStatus?.enabled ? 'Stop' : 'Start'}
        </button>

        {/* Interval */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-slate-500">Interval:</label>
          <input
            type="number"
            min={5}
            max={1440}
            value={intervalInput}
            onChange={(e) => onIntervalChange(Math.max(5, Math.min(1440, Number(e.target.value) || 5)))}
            className="w-20 border border-slate-200 rounded-lg px-2.5 py-1.5 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center"
          />
          <span className="text-xs text-slate-400">min</span>
        </div>

        {/* Auto-analyze Toggle */}
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <div
            onClick={onAutoAnalyzeToggle}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
              autoAnalyze ? 'bg-blue-600' : 'bg-slate-300'
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform shadow-sm ${
                autoAnalyze ? 'translate-x-4' : 'translate-x-0.5'
              }`}
            />
          </div>
          <span className="text-xs font-medium text-slate-600">Auto-analyze</span>
        </label>

        <div className="border-l border-slate-200 h-8 mx-1" />

        {/* Poll Now */}
        <button
          onClick={onPollNow}
          disabled={pollNowLoading}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 shadow-sm transition-colors"
        >
          {pollNowLoading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          Poll Now
        </button>
      </div>

      {/* Status Row */}
      {pollerStatus && (
        <div className="mt-4 flex items-center gap-6 text-xs text-slate-500">
          <span>
            Last poll: <strong className="text-slate-700">{timeAgo(pollerStatus.last_poll)}</strong>
          </span>
          {pollerStatus.enabled && pollerStatus.next_poll && (
            <span>
              Next: <strong className="text-slate-700">{timeUntil(pollerStatus.next_poll)}</strong>
            </span>
          )}
          <span>
            Polls: <strong className="text-slate-700">{pollerStatus.poll_count}</strong>
          </span>
          {pollerStatus.error_count > 0 && (
            <span className="text-red-500">
              Errors: <strong>{pollerStatus.error_count}</strong>
            </span>
          )}
          {pollerStatus.last_error && (
            <span className="text-red-500 truncate max-w-[300px]" title={pollerStatus.last_error}>
              Last error: {pollerStatus.last_error}
            </span>
          )}
        </div>
      )}

      {/* Recent Activity Log */}
      <PollLog pollLog={pollLog} />
    </div>
  )
}
