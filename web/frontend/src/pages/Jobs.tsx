import { useEffect, useState, useCallback, useMemo } from 'react'
import type { ProgressEvent, AnalysisJob } from '../types'
import { useAnalysisStore } from '../stores/analysisStore'
import { useWebSocket } from '../hooks/useWebSocket'
import type { WSMessage } from '../hooks/useWebSocket'
import { api } from '../api/client'
import { formatDate, formatDurationSec } from '../utils/format'
import StatusBadge from '../components/StatusBadge'
import AnalysisLog from '../components/AnalysisLog'
import ProgressTimeline from '../components/ProgressTimeline'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'
import { usePagination } from '../hooks/usePagination'
import Pagination from '../components/ui/Pagination'

type LogView = 'progress' | 'raw'

function ElapsedTime({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState(() =>
    Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
  )

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [startedAt])

  return <span className="text-xs text-slate-500 font-mono">{formatDurationSec(elapsed)}</span>
}

function JobRow({
  job,
  isSelected,
  isLast,
  onSelect,
  onCancel,
  cancelLoading,
}: {
  job: AnalysisJob
  isSelected: boolean
  isLast: boolean
  onSelect: () => void
  onCancel?: () => void
  cancelLoading: boolean
}) {
  const isRunning = job.status === 'running' || job.status === 'pending'
  const duration =
    !isRunning && job.started_at && job.finished_at
      ? Math.round((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)
      : null

  return (
    <div
      className={`px-5 py-3 flex items-center justify-between cursor-pointer transition-colors ${
        isSelected
          ? 'bg-blue-50 border-l-2 border-l-blue-500'
          : 'hover:bg-slate-50 border-l-2 border-l-transparent'
      } ${!isLast ? 'border-b border-slate-100' : ''}`}
      onClick={onSelect}
    >
      <div className="flex items-center gap-3">
        <StatusBadge status={job.status} />
        <span className="text-sm font-semibold text-slate-800">{job.task_id}</span>
        <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded">{job.mode}</span>
        <span className="text-xs text-slate-400 font-mono">{job.id.substring(0, 8)}</span>
      </div>
      <div className="flex items-center gap-3">
        {isRunning && job.started_at && <ElapsedTime startedAt={job.started_at} />}
        {!isRunning && duration !== null && (
          <span className="text-xs text-slate-500 font-mono">{formatDurationSec(duration)}</span>
        )}
        {job.started_at && (
          <span className="text-xs text-slate-400">{formatDate(job.started_at)}</span>
        )}
        {isRunning && onCancel && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onCancel()
            }}
            disabled={cancelLoading}
            className="px-2.5 py-1 text-xs text-red-600 hover:text-red-800 font-medium border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50 flex items-center gap-1 transition-colors"
          >
            {cancelLoading && <LoadingSpinner size="sm" />}
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}

export default function Jobs() {
  const { jobs, history, activeJobOutput, progressEvents, selectedJobId, fetchJobs, fetchHistory, addOutputLine, addProgressEvent, updateJob, updateJobMode, selectJob, clearCompletedJobs } =
    useAnalysisStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelLoading, setCancelLoading] = useState<string | null>(null)
  const [clearLoading, setClearLoading] = useState(false)
  const [logView, setLogView] = useState<LogView>('progress')

  const handleWsMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case 'job_started':
          updateJob(msg.job)
          selectJob(msg.job_id)
          break
        case 'output':
          addOutputLine(msg.job_id, msg.line)
          break
        case 'progress':
          // cleanup events are transient (post-result process teardown) — don't persist
          if (msg.event === 'cleanup') break
          addProgressEvent(msg.job_id, {
            event: msg.event as ProgressEvent['event'],
            tool: msg.tool,
            detail: msg.detail,
            subtype: msg.subtype,
            duration_ms: msg.duration_ms,
            num_turns: msg.num_turns,
            cost_usd: msg.cost_usd,
            timestamp: msg.timestamp,
          })
          break
        case 'job_finished':
          updateJob(msg.job)
          fetchHistory()
          break
        case 'mode_resolved':
          updateJobMode(msg.job_id, msg.resolved_mode)
          break
      }
    },
    [updateJob, updateJobMode, selectJob, addOutputLine, addProgressEvent, fetchHistory]
  )

  useWebSocket(handleWsMessage)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        await Promise.all([fetchJobs(), fetchHistory()])
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [fetchJobs, fetchHistory])

  useEffect(() => {
    const hasRunning = jobs.some((j) => j.status === 'running' || j.status === 'pending')
    if (!hasRunning) return
    const interval = setInterval(() => {
      fetchJobs()
      fetchHistory()
    }, 5000)
    return () => clearInterval(interval)
  }, [jobs, fetchJobs, fetchHistory])

  const handleCancelJob = async (jobId: string) => {
    setCancelLoading(jobId)
    try {
      await api.cancelJob(jobId)
      await fetchJobs()
    } catch (e) {
      console.error('Failed to cancel job:', e)
    } finally {
      setCancelLoading(null)
    }
  }

  const handleClearCompleted = async () => {
    setClearLoading(true)
    try {
      await clearCompletedJobs()
    } finally {
      setClearLoading(false)
    }
  }

  const runningJobs = useMemo(
    () => jobs.filter((j) => j.status === 'running' || j.status === 'pending'),
    [jobs]
  )
  const recentJobs = useMemo(
    () => jobs.filter((j) => j.status !== 'running' && j.status !== 'pending'),
    [jobs]
  )

  const selectedLines = selectedJobId ? activeJobOutput[selectedJobId] || [] : []
  const selectedProgress = selectedJobId ? progressEvents[selectedJobId] || [] : []
  const selectedJob = selectedJobId ? jobs.find((j) => j.id === selectedJobId) : null
  const isSelectedRunning = selectedJob?.status === 'running'

  const historyPg = usePagination(history, 20)

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div>
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-800">Jobs</h1>
        <p className="text-sm text-slate-500 mt-0.5">Monitor analysis jobs and view history</p>
      </div>

      {error && (
        <div className="mb-5">
          <ErrorMessage message={error} />
        </div>
      )}

      {/* Active Jobs */}
      <div className="bg-white rounded-xl border border-slate-200 mb-5 overflow-hidden">
        {/* Running section */}
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-800">Running</h2>
            {runningJobs.length > 0 && (
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
                {runningJobs.length}
              </span>
            )}
          </div>
        </div>
        {runningJobs.length === 0 ? (
          <div className="px-5 py-6 text-center border-b border-slate-100">
            <p className="text-sm text-slate-400">No running jobs</p>
          </div>
        ) : (
          <div className="border-b border-slate-100">
            {runningJobs.map((job, idx) => (
              <JobRow
                key={job.id}
                job={job}
                isSelected={selectedJobId === job.id}
                isLast={idx === runningJobs.length - 1}
                onSelect={() => selectJob(job.id)}
                onCancel={() => handleCancelJob(job.id)}
                cancelLoading={cancelLoading === job.id}
              />
            ))}
          </div>
        )}

        {/* Recent section */}
        {recentJobs.length > 0 && (
          <>
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-800">Recent</h2>
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-600 text-xs font-bold">
                  {recentJobs.length}
                </span>
              </div>
              <button
                onClick={handleClearCompleted}
                disabled={clearLoading}
                className="px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700 font-medium border border-slate-200 rounded-lg hover:bg-slate-100 disabled:opacity-50 flex items-center gap-1 transition-colors"
              >
                {clearLoading && <LoadingSpinner size="sm" />}
                Clear completed
              </button>
            </div>
            <div>
              {recentJobs.map((job, idx) => (
                <JobRow
                  key={job.id}
                  job={job}
                  isSelected={selectedJobId === job.id}
                  isLast={idx === recentJobs.length - 1}
                  onSelect={() => selectJob(job.id)}
                  cancelLoading={false}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Log Viewer */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-800">Output</h2>
            {selectedJobId && (
              <span className="text-xs text-slate-400 font-mono bg-slate-100 px-2 py-0.5 rounded">
                {selectedJobId.substring(0, 8)}
              </span>
            )}
          </div>
          <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
            <button
              onClick={() => setLogView('progress')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                logView === 'progress'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Progress
            </button>
            <button
              onClick={() => setLogView('raw')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                logView === 'raw'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Raw Output
            </button>
          </div>
        </div>
        {logView === 'progress' ? (
          <ProgressTimeline events={selectedProgress} isRunning={isSelectedRunning} />
        ) : (
          <AnalysisLog lines={selectedLines} />
        )}
      </div>

      {/* History */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">History</h2>
        </div>
        {history.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <p className="text-sm text-slate-500">No analysis history</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Task</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Mode</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Status</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Started</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Duration</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Exit</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Lines</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Info</th>
                </tr>
              </thead>
              <tbody>
                {historyPg.paginated.map((entry, idx) => {
                  const duration =
                    entry.started_at && entry.finished_at
                      ? Math.round(
                          (new Date(entry.finished_at).getTime() - new Date(entry.started_at).getTime()) / 1000
                        )
                      : null
                  const durationStr = formatDurationSec(duration)
                  return (
                    <tr
                      key={entry.id}
                      className={`hover:bg-slate-50 transition-colors ${
                        idx !== historyPg.paginated.length - 1 ? 'border-b border-slate-100' : ''
                      }`}
                    >
                      <td className="px-4 py-2.5 text-sm font-semibold text-slate-800">{entry.task_id}</td>
                      <td className="px-4 py-2.5">
                        <span className="text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded">{entry.mode}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={entry.status} />
                      </td>
                      <td className="px-4 py-2.5 text-sm text-slate-600">
                        {new Date(entry.started_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-sm text-slate-600 font-mono">{durationStr}</td>
                      <td className="px-4 py-2.5 text-sm">
                        {entry.exit_code !== null ? (
                          <span
                            className={`inline-flex items-center justify-center px-1.5 h-6 rounded-md text-xs font-bold cursor-help ${
                              entry.exit_code === 0
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'bg-red-100 text-red-700'
                            }`}
                            title={entry.exit_reason || (entry.exit_code === 0 ? 'success' : `exit code ${entry.exit_code}`)}
                          >
                            {entry.exit_code === 0
                              ? '0'
                              : entry.exit_code > 0x80000000 || entry.exit_code < 0
                                ? `0x${((entry.exit_code < 0 ? entry.exit_code >>> 0 : entry.exit_code)).toString(16).toUpperCase()}`
                                : entry.exit_code}
                          </span>
                        ) : (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-sm text-slate-600">{entry.output_line_count}</td>
                      <td className="px-4 py-2.5 text-sm">
                        <div className="flex items-center gap-2">
                          {entry.retry_job_id && (
                            <span className="text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded" title={`Retried as ${entry.retry_job_id}`}>
                              retried
                            </span>
                          )}
                          {entry.session_id && (
                            <span className="text-xs text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded" title={`Session: ${entry.session_id}`}>
                              session
                            </span>
                          )}
                          {entry.status === 'failed' && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                window.open(`/api/analysis/jobs/${entry.id}/log`, '_blank')
                              }}
                              className="text-xs text-slate-500 hover:text-slate-700 underline"
                              title="View persisted output log"
                            >
                              log
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pagination page={historyPg.page} totalPages={historyPg.totalPages} totalItems={historyPg.totalItems} pageSize={historyPg.pageSize} onPageChange={historyPg.setPage} />
          </div>
        )}
      </div>
    </div>
  )
}
