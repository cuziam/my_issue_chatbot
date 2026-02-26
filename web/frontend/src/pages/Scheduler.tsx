import { useEffect, useState, useCallback } from 'react'
import type { StateData, Trigger, PollerStatus, PollLogEntry } from '../types'
import { api } from '../api/client'
import { useWebSocketContext } from '../contexts/WebSocketContext'
import StatusBadge from '../components/StatusBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'
import { usePagination } from '../hooks/usePagination'
import Pagination from '../components/ui/Pagination'

function timeAgo(iso: string | null): string {
  if (!iso) return '-'
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 0) return 'just now'
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function timeUntil(iso: string | null): string {
  if (!iso) return '-'
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return 'now'
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

export default function Scheduler() {
  // State
  const [state, setState] = useState<StateData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Poller
  const [pollerStatus, setPollerStatus] = useState<PollerStatus | null>(null)
  const [pollerLoading, setPollerLoading] = useState(false)
  const [intervalInput, setIntervalInput] = useState(30)
  const [autoAnalyze, setAutoAnalyze] = useState(true)
  const [pollNowLoading, setPollNowLoading] = useState(false)

  // Triggers (manual detect + pending from poller)
  const [manualTriggers, setManualTriggers] = useState<Trigger[] | null>(null)
  const [detectLoading, setDetectLoading] = useState(false)
  const [detectApiCount, setDetectApiCount] = useState<number | null>(null)

  // Trigger management
  const [selectedTriggers, setSelectedTriggers] = useState<Set<string>>(new Set())
  const [analyzeLoading, setAnalyzeLoading] = useState<string | null>(null) // task_id being analyzed, or 'bulk'

  // Other
  const [initLoading, setInitLoading] = useState(false)
  const [initResult, setInitResult] = useState<string | null>(null)
  const [resetLoading, setResetLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Poll log from WS
  const [pollLog, setPollLog] = useState<PollLogEntry[]>([])

  // Timer for updating relative times
  const [, setTick] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 10000)
    return () => clearInterval(interval)
  }, [])

  const loadState = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getState()
      setState(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load state')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadPollerStatus = useCallback(async () => {
    try {
      const status = await api.getPollerStatus()
      setPollerStatus(status)
      setIntervalInput(status.interval_minutes)
      setAutoAnalyze(status.auto_analyze)
      if (status.poll_log?.length) {
        setPollLog(status.poll_log)
      }
    } catch {
      // Poller endpoint may not exist yet — ignore
    }
  }, [])

  useEffect(() => {
    loadState()
    loadPollerStatus()
  }, [loadState, loadPollerStatus])

  // WebSocket handler
  useWebSocketContext(useCallback((msg) => {
    if (msg.type === 'scheduler_status') {
      setPollerStatus(msg.status)
    } else if (msg.type === 'scheduler_poll_started') {
      setPollNowLoading(false)
    } else if (msg.type === 'scheduler_poll_completed') {
      const result = msg.result
      setPollLog((prev) => {
        const entry: PollLogEntry = {
          poll_count: result.trigger_count,
          timestamp: msg.timestamp,
          status: result.status,
          trigger_count: result.trigger_count,
          started_jobs_count: result.started_jobs?.length ?? 0,
          error: result.message,
        }
        const updated = [...prev, entry]
        return updated.slice(-20)
      })
      setPollNowLoading(false)
      // Refresh state after poll
      loadState()
    } else if (msg.type === 'job_finished') {
      loadState()
    }
  }, [loadState]))

  // ---- Poller controls ----
  const handleTogglePoller = async () => {
    setPollerLoading(true)
    setActionError(null)
    try {
      if (pollerStatus?.enabled) {
        await api.stopPoller()
      } else {
        await api.startPoller(intervalInput, autoAnalyze)
      }
      await loadPollerStatus()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to toggle poller')
    } finally {
      setPollerLoading(false)
    }
  }

  const handleIntervalChange = async (val: number) => {
    setIntervalInput(val)
    if (pollerStatus?.enabled) {
      try {
        await api.updatePollerConfig(val, undefined)
      } catch { /* ignore */ }
    }
  }

  const handleAutoAnalyzeToggle = async () => {
    const newVal = !autoAnalyze
    setAutoAnalyze(newVal)
    if (pollerStatus?.enabled) {
      try {
        await api.updatePollerConfig(undefined, newVal)
      } catch { /* ignore */ }
    }
  }

  const handlePollNow = async () => {
    setPollNowLoading(true)
    setActionError(null)
    try {
      await api.pollNow()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to poll')
    } finally {
      setPollNowLoading(false)
    }
  }

  // ---- Detect triggers (manual) ----
  const handleDetect = async () => {
    setDetectLoading(true)
    setActionError(null)
    setManualTriggers(null)
    setDetectApiCount(null)
    try {
      const result = await api.detectTriggers()
      setManualTriggers(result.triggers)
      setDetectApiCount(result.api_task_count)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to detect triggers')
    } finally {
      setDetectLoading(false)
    }
  }

  const handleInitState = async () => {
    setInitLoading(true)
    setActionError(null)
    setInitResult(null)
    try {
      const result = await api.initState()
      setInitResult(`State initialized with ${result.task_count} tasks`)
      loadState()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to init state')
    } finally {
      setInitLoading(false)
    }
  }

  const handleResetAttempts = async (taskId: string) => {
    setResetLoading(taskId)
    setActionError(null)
    try {
      await api.resetAttempts(taskId)
      loadState()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to reset attempts')
    } finally {
      setResetLoading(null)
    }
  }

  // ---- Trigger management ----
  const allTriggers = [
    ...(pollerStatus?.pending_triggers ?? []),
    ...(manualTriggers ?? []),
  ]
  // Deduplicate
  const triggerKey = (t: Trigger) => `${t.custom_id || t.task_id}:${t.mode}`
  const seenKeys = new Set<string>()
  const dedupedTriggers = allTriggers.filter((t) => {
    const key = triggerKey(t)
    if (seenKeys.has(key)) return false
    seenKeys.add(key)
    return true
  })

  const handleSelectTrigger = (t: Trigger) => {
    const key = triggerKey(t)
    setSelectedTriggers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleSelectAll = () => {
    if (selectedTriggers.size === dedupedTriggers.length) {
      setSelectedTriggers(new Set())
    } else {
      setSelectedTriggers(new Set(dedupedTriggers.map(triggerKey)))
    }
  }

  const handleAnalyzeTrigger = async (t: Trigger) => {
    const key = triggerKey(t)
    setAnalyzeLoading(key)
    setActionError(null)
    try {
      await api.analyzeTriggers([{ task_id: t.task_id, custom_id: t.custom_id, mode: t.mode, reason: t.reason }])
      // Remove from manual triggers
      setManualTriggers((prev) => prev?.filter((x) => triggerKey(x) !== key) ?? null)
      setSelectedTriggers((prev) => { const n = new Set(prev); n.delete(key); return n })
      await loadPollerStatus()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to start analysis')
    } finally {
      setAnalyzeLoading(null)
    }
  }

  const handleDismissTrigger = async (t: Trigger) => {
    setActionError(null)
    try {
      await api.dismissTriggers([{ task_id: t.custom_id || t.task_id, mode: t.mode }])
      setManualTriggers((prev) => prev?.filter((x) => triggerKey(x) !== triggerKey(t)) ?? null)
      setSelectedTriggers((prev) => { const n = new Set(prev); n.delete(triggerKey(t)); return n })
      await loadPollerStatus()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to dismiss trigger')
    }
  }

  const handleAnalyzeSelected = async () => {
    const selected = dedupedTriggers.filter((t) => selectedTriggers.has(triggerKey(t)))
    if (selected.length === 0) return
    setAnalyzeLoading('bulk')
    setActionError(null)
    try {
      await api.analyzeTriggers(
        selected.map((t) => ({ task_id: t.task_id, custom_id: t.custom_id, mode: t.mode, reason: t.reason }))
      )
      const selectedKeys = new Set(selected.map(triggerKey))
      setManualTriggers((prev) => prev?.filter((x) => !selectedKeys.has(triggerKey(x))) ?? null)
      setSelectedTriggers(new Set())
      await loadPollerStatus()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to start analyses')
    } finally {
      setAnalyzeLoading(null)
    }
  }

  // Pagination
  const taskEntries = state ? Object.entries(state.tasks) : []
  const statePg = usePagination(taskEntries, 20)
  const triggersPg = usePagination(dedupedTriggers, 20)

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={loadState} />
  }

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Scheduler</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage automated trigger detection and analysis</p>
        </div>
        {state?.last_run && (
          <div className="text-right">
            <p className="text-xs text-slate-400">Last state update</p>
            <p className="text-sm text-slate-600 font-medium">{new Date(state.last_run).toLocaleString()}</p>
          </div>
        )}
      </div>

      {actionError && (
        <div className="mb-5">
          <ErrorMessage message={actionError} />
        </div>
      )}

      {/* Poller Control Card */}
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
            onClick={handleTogglePoller}
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
              onChange={(e) => handleIntervalChange(Math.max(5, Math.min(1440, Number(e.target.value) || 5)))}
              className="w-20 border border-slate-200 rounded-lg px-2.5 py-1.5 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center"
            />
            <span className="text-xs text-slate-400">min</span>
          </div>

          {/* Auto-analyze Toggle */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div
              onClick={handleAutoAnalyzeToggle}
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
            onClick={handlePollNow}
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
        {pollLog.length > 0 && (
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
        )}
      </div>

      {/* Actions Card (Detect + Init) */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <h2 className="text-sm font-semibold text-slate-800">Manual Actions</h2>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={handleDetect}
            disabled={detectLoading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 shadow-sm transition-colors"
          >
            {detectLoading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            )}
            Detect Triggers
          </button>
          <div className="border-l border-slate-200 h-8 mx-1" />
          <button
            onClick={handleInitState}
            disabled={initLoading}
            className="inline-flex items-center gap-2 px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {initLoading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
            Init State
          </button>
        </div>

        {initResult && (
          <div className="mt-3 px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
            {initResult}
          </div>
        )}
      </div>

      {/* Detected Triggers */}
      {dedupedTriggers.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 mb-5 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-800">Detected Triggers</h2>
              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-bold bg-amber-100 text-amber-700">
                {dedupedTriggers.length}
              </span>
              {detectApiCount !== null && (
                <span className="text-xs text-slate-400 ml-2">{detectApiCount} tasks from API</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSelectAll}
                className="text-xs text-slate-500 hover:text-blue-600 font-medium transition-colors"
              >
                {selectedTriggers.size === dedupedTriggers.length ? 'Deselect All' : 'Select All'}
              </button>
              {selectedTriggers.size > 0 && (
                <button
                  onClick={handleAnalyzeSelected}
                  disabled={analyzeLoading === 'bulk'}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-xs font-medium disabled:opacity-50 shadow-sm transition-colors"
                >
                  {analyzeLoading === 'bulk' && <LoadingSpinner size="sm" />}
                  Analyze Selected ({selectedTriggers.size})
                </button>
              )}
            </div>
          </div>
          <table className="min-w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-3 py-2.5 text-center w-10">
                  <input
                    type="checkbox"
                    checked={selectedTriggers.size === dedupedTriggers.length && dedupedTriggers.length > 0}
                    onChange={handleSelectAll}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                </th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Task</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Custom ID</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Mode</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Reason</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {triggersPg.paginated.map((t, idx) => {
                const key = triggerKey(t)
                return (
                  <tr
                    key={key}
                    className={`hover:bg-slate-50 transition-colors ${
                      idx !== triggersPg.paginated.length - 1 ? 'border-b border-slate-100' : ''
                    }`}
                  >
                    <td className="px-3 py-2.5 text-center">
                      <input
                        type="checkbox"
                        checked={selectedTriggers.has(key)}
                        onChange={() => handleSelectTrigger(t)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-3 py-2.5 text-sm font-semibold text-slate-800">{t.task_id.slice(0, 8)}</td>
                    <td className="px-3 py-2.5 text-sm text-slate-600 font-mono">{t.custom_id || '-'}</td>
                    <td className="px-3 py-2.5">
                      <StatusBadge status={t.mode} />
                    </td>
                    <td className="px-3 py-2.5 text-sm text-slate-600">{t.reason}</td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleAnalyzeTrigger(t)}
                          disabled={analyzeLoading === key}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg hover:bg-emerald-100 text-xs font-medium disabled:opacity-50 transition-colors"
                          title="Analyze this trigger"
                        >
                          {analyzeLoading === key ? (
                            <LoadingSpinner size="sm" />
                          ) : (
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                            </svg>
                          )}
                        </button>
                        <button
                          onClick={() => handleDismissTrigger(t)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-50 text-slate-500 border border-slate-200 rounded-lg hover:bg-red-50 hover:text-red-600 hover:border-red-200 text-xs font-medium transition-colors"
                          title="Dismiss this trigger"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <Pagination page={triggersPg.page} totalPages={triggersPg.totalPages} totalItems={triggersPg.totalItems} pageSize={triggersPg.pageSize} onPageChange={triggersPg.setPage} />
        </div>
      )}

      {/* Empty triggers result from manual detect */}
      {manualTriggers !== null && dedupedTriggers.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 mb-5 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-800">Detected Triggers</h2>
              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-bold bg-slate-100 text-slate-500">0</span>
            </div>
            {detectApiCount !== null && (
              <span className="text-xs text-slate-400">{detectApiCount} tasks from API</span>
            )}
          </div>
          <div className="px-5 py-8 text-center">
            <svg className="w-8 h-8 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-slate-500">No triggers detected</p>
          </div>
        </div>
      )}

      {/* State Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-800">State</h2>
            <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
              {taskEntries.length} tasks
            </span>
          </div>
          <button
            onClick={loadState}
            className="text-xs text-slate-500 hover:text-blue-600 font-medium transition-colors inline-flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>
        {taskEntries.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <svg className="w-10 h-10 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
            </svg>
            <p className="text-sm text-slate-500">No state data</p>
            <p className="text-xs text-slate-400 mt-1">Click "Init State" to initialize</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Task ID</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Status</th>
                  <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-500 uppercase">Report</th>
                  <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-500 uppercase">Patch</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Last Analysis</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Last Time</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Attempts</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {statePg.paginated.map(([taskId, taskState], idx) => {
                  const attemptsStr = Object.entries(taskState.trigger_attempts)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(', ')
                  return (
                    <tr
                      key={taskId}
                      className={`hover:bg-slate-50 transition-colors ${
                        idx !== statePg.paginated.length - 1 ? 'border-b border-slate-100' : ''
                      }`}
                    >
                      <td className="px-3 py-2.5 text-sm font-semibold text-slate-800 whitespace-nowrap">{taskId}</td>
                      <td className="px-3 py-2.5">
                        <StatusBadge status={taskState.status} />
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        {taskState.has_report ? (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                            Yes
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        {taskState.has_patch_review ? (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                            Yes
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        {taskState.last_analysis_type ? (
                          <span className="text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                            {taskState.last_analysis_type}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-sm text-slate-600 whitespace-nowrap">
                        {taskState.last_analysis_time
                          ? new Date(taskState.last_analysis_time).toLocaleString()
                          : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-3 py-2.5">
                        {attemptsStr ? (
                          <span className="text-xs text-slate-600 font-mono bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
                            {attemptsStr}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-right whitespace-nowrap">
                        <button
                          onClick={() => handleResetAttempts(taskId)}
                          disabled={resetLoading === taskId}
                          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-blue-600 font-medium disabled:opacity-50 transition-colors"
                        >
                          {resetLoading === taskId && <LoadingSpinner size="sm" />}
                          Reset
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pagination page={statePg.page} totalPages={statePg.totalPages} totalItems={statePg.totalItems} pageSize={statePg.pageSize} onPageChange={statePg.setPage} />
          </div>
        )}
      </div>
    </div>
  )
}
