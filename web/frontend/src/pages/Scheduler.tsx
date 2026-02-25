import { useEffect, useState, useCallback } from 'react'
import type { StateData, Trigger } from '../types'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'
import ConfirmDialog from '../components/ConfirmDialog'
import { usePagination } from '../hooks/usePagination'
import Pagination from '../components/ui/Pagination'

export default function Scheduler() {
  const [state, setState] = useState<StateData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [triggers, setTriggers] = useState<Trigger[] | null>(null)
  const [detectLoading, setDetectLoading] = useState(false)
  const [detectApiCount, setDetectApiCount] = useState<number | null>(null)

  const [runOutput, setRunOutput] = useState<{ stdout: string; stderr: string } | null>(null)
  const [runLoading, setRunLoading] = useState(false)

  const [confirmRealRun, setConfirmRealRun] = useState(false)
  const [initLoading, setInitLoading] = useState(false)
  const [initResult, setInitResult] = useState<string | null>(null)

  const [resetLoading, setResetLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

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

  useEffect(() => {
    loadState()
  }, [loadState])

  const handleDetect = async () => {
    setDetectLoading(true)
    setActionError(null)
    setTriggers(null)
    setDetectApiCount(null)
    try {
      const result = await api.detectTriggers()
      setTriggers(result.triggers)
      setDetectApiCount(result.api_task_count)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to detect triggers')
    } finally {
      setDetectLoading(false)
    }
  }

  const handleRun = async (dryRun: boolean) => {
    setRunLoading(true)
    setRunOutput(null)
    setActionError(null)
    setConfirmRealRun(false)
    try {
      const result = await api.runScheduler(dryRun)
      setRunOutput({ stdout: result.stdout, stderr: result.stderr })
      if (!dryRun) {
        loadState()
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to run scheduler')
    } finally {
      setRunLoading(false)
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

  const taskEntries = state ? Object.entries(state.tasks) : []
  const statePg = usePagination(taskEntries, 20)
  const triggersPg = usePagination(triggers ?? [], 20)

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
            <p className="text-xs text-slate-400">Last run</p>
            <p className="text-sm text-slate-600 font-medium">{new Date(state.last_run).toLocaleString()}</p>
          </div>
        )}
      </div>

      {actionError && (
        <div className="mb-5">
          <ErrorMessage message={actionError} />
        </div>
      )}

      {/* Action Buttons */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h2 className="text-sm font-semibold text-slate-800">Actions</h2>
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
          <button
            onClick={() => handleRun(true)}
            disabled={runLoading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-800 text-sm font-medium disabled:opacity-50 shadow-sm transition-colors"
          >
            {runLoading && <LoadingSpinner size="sm" />}
            Dry Run
          </button>
          <button
            onClick={() => setConfirmRealRun(true)}
            disabled={runLoading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm font-medium disabled:opacity-50 shadow-sm transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Run (Real)
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

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmRealRun}
        title="Run Scheduler (Real)"
        message="This will execute the scheduler for real and trigger actual analyses. Are you sure?"
        confirmLabel="Run"
        variant="danger"
        onConfirm={() => handleRun(false)}
        onCancel={() => setConfirmRealRun(false)}
      />

      {/* Triggers Result */}
      {triggers !== null && (
        <div className="bg-white rounded-xl border border-slate-200 mb-5 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-800">Detected Triggers</h2>
              <span className={`inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-bold ${
                triggers.length > 0 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
              }`}>
                {triggers.length}
              </span>
            </div>
            {detectApiCount !== null && (
              <span className="text-xs text-slate-400">{detectApiCount} tasks from API</span>
            )}
          </div>
          {triggers.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <svg className="w-8 h-8 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-slate-500">No triggers detected</p>
            </div>
          ) : (
            <>
              <table className="min-w-full">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Task</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Custom ID</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Mode</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {triggersPg.paginated.map((t, idx) => (
                    <tr
                      key={idx}
                      className={`hover:bg-slate-50 transition-colors ${
                        idx !== triggersPg.paginated.length - 1 ? 'border-b border-slate-100' : ''
                      }`}
                    >
                      <td className="px-4 py-2.5 text-sm font-semibold text-slate-800">{t.task_id}</td>
                      <td className="px-4 py-2.5 text-sm text-slate-600 font-mono">{t.custom_id}</td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={t.mode} />
                      </td>
                      <td className="px-4 py-2.5 text-sm text-slate-600">{t.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination page={triggersPg.page} totalPages={triggersPg.totalPages} totalItems={triggersPg.totalItems} pageSize={triggersPg.pageSize} onPageChange={triggersPg.setPage} />
            </>
          )}
        </div>
      )}

      {/* Run Output */}
      {runOutput && (
        <div className="mb-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-3">Scheduler Output</h2>
          <div className="space-y-3">
            {runOutput.stdout && (
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-xs font-medium text-slate-500">stdout</span>
                </div>
                <pre className="bg-slate-900 text-emerald-400 font-mono text-[0.8rem] leading-relaxed p-4 rounded-xl border border-slate-700 overflow-auto max-h-[400px] whitespace-pre-wrap scrollbar-dark">
                  {runOutput.stdout}
                </pre>
              </div>
            )}
            {runOutput.stderr && (
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  <span className="text-xs font-medium text-slate-500">stderr</span>
                </div>
                <pre className="bg-slate-900 text-red-400 font-mono text-[0.8rem] leading-relaxed p-4 rounded-xl border border-slate-700 overflow-auto max-h-[400px] whitespace-pre-wrap scrollbar-dark">
                  {runOutput.stderr}
                </pre>
              </div>
            )}
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
