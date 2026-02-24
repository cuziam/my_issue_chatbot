import { useEffect, useState, useCallback } from 'react'
import { useAnalysisStore } from '../stores/analysisStore'
import { useWebSocket } from '../hooks/useWebSocket'
import type { WSMessage } from '../hooks/useWebSocket'
import type { AnalysisMode } from '../types'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import AnalysisLog from '../components/AnalysisLog'
import ProgressTimeline from '../components/ProgressTimeline'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'

const ANALYSIS_MODES: { value: AnalysisMode; label: string; desc: string }[] = [
  { value: 'initial', label: 'Initial Analysis', desc: 'Researcher + Analyzer team으로 이슈 최초 분석 → report.md 생성' },
  { value: 'review', label: 'QA Review', desc: '개발자 수정 후 검증. 패치 있으면 자동 패치 리뷰, 없으면 verification 수행' },
  { value: 'activity_update', label: 'Activity Update', desc: '새 댓글/본문 변경 감지 후 팔로업. report.md에 추가 분석 append' },
]

type LogView = 'progress' | 'raw'

export default function Analysis() {
  const { jobs, history, activeJobOutput, progressEvents, selectedJobId, fetchJobs, fetchHistory, addOutputLine, addProgressEvent, updateJob, updateJobMode, selectJob } =
    useAnalysisStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [taskIdInput, setTaskIdInput] = useState('')
  const [selectedMode, setSelectedMode] = useState<AnalysisMode>('initial')
  const [startLoading, setStartLoading] = useState(false)
  const [cancelLoading, setCancelLoading] = useState<string | null>(null)
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
          addProgressEvent(msg.job_id, {
            event: msg.event as 'tool_use' | 'text' | 'result',
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

  // Fallback polling: refresh jobs every 5s while any job is running.
  // This ensures progress_events are loaded even if WebSocket is down.
  useEffect(() => {
    const hasRunning = jobs.some((j) => j.status === 'running' || j.status === 'pending')
    if (!hasRunning) return
    const interval = setInterval(() => {
      fetchJobs()
      fetchHistory()
    }, 5000)
    return () => clearInterval(interval)
  }, [jobs, fetchJobs, fetchHistory])

  const handleStartAnalysis = async () => {
    if (!taskIdInput.trim()) return
    setStartLoading(true)
    try {
      const job = await api.startAnalysis(taskIdInput.trim(), selectedMode)
      // Pre-validation error (no job spawned)
      if ((job as unknown as Record<string, unknown>).status === 'error') {
        setError((job as unknown as Record<string, unknown>).message as string || 'Failed to start analysis')
      } else {
        updateJob(job)
        selectJob(job.id)
        setTaskIdInput('')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start analysis')
    } finally {
      setStartLoading(false)
    }
  }

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

  const selectedLines = selectedJobId ? activeJobOutput[selectedJobId] || [] : []
  const selectedProgress = selectedJobId ? progressEvents[selectedJobId] || [] : []
  const selectedJob = selectedJobId ? jobs.find((j) => j.id === selectedJobId) : null
  const isSelectedRunning = selectedJob?.status === 'running'

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const activeJobs = jobs.filter((j) => j.status === 'running' || j.status === 'pending')

  return (
    <div>
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-800">Analysis</h1>
        <p className="text-sm text-slate-500 mt-0.5">Start and monitor AI-powered issue analysis</p>
      </div>

      {error && (
        <div className="mb-5">
          <ErrorMessage message={error} />
        </div>
      )}

      {/* Start Analysis Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-sm font-semibold text-slate-800">Start Analysis</h2>
        </div>
        <div className="flex items-end gap-3">
          <div className="flex-shrink-0">
            <label className="block text-xs font-medium text-slate-500 mb-1.5">Task ID</label>
            <input
              type="text"
              value={taskIdInput}
              onChange={(e) => setTaskIdInput(e.target.value)}
              placeholder="e.g. IMX-9355"
              className="border border-slate-200 rounded-lg px-3.5 py-2 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent w-48"
              onKeyDown={(e) => e.key === 'Enter' && handleStartAnalysis()}
            />
          </div>
          <div className="flex-shrink-0">
            <label className="block text-xs font-medium text-slate-500 mb-1.5">Mode</label>
            <select
              value={selectedMode}
              onChange={(e) => setSelectedMode(e.target.value as AnalysisMode)}
              className="border border-slate-200 rounded-lg px-3.5 py-2 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {ANALYSIS_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleStartAnalysis}
            disabled={startLoading || !taskIdInput.trim()}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm transition-colors"
          >
            {startLoading && <LoadingSpinner size="sm" />}
            Start
          </button>
        </div>
        {/* Mode description */}
        <p className="mt-3 text-xs text-slate-400">
          {ANALYSIS_MODES.find((m) => m.value === selectedMode)?.desc}
        </p>
      </div>

      {/* Active Jobs */}
      <div className="bg-white rounded-xl border border-slate-200 mb-5 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-800">Active Jobs</h2>
            {activeJobs.length > 0 && (
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
                {activeJobs.length}
              </span>
            )}
          </div>
        </div>
        {jobs.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <svg className="w-8 h-8 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            <p className="text-sm text-slate-500">No active jobs</p>
          </div>
        ) : (
          <div>
            {jobs.map((job, idx) => (
              <div
                key={job.id}
                className={`px-5 py-3 flex items-center justify-between cursor-pointer transition-colors ${
                  selectedJobId === job.id
                    ? 'bg-blue-50 border-l-2 border-l-blue-500'
                    : 'hover:bg-slate-50 border-l-2 border-l-transparent'
                } ${idx !== jobs.length - 1 ? 'border-b border-slate-100' : ''}`}
                onClick={() => selectJob(job.id)}
              >
                <div className="flex items-center gap-3">
                  <StatusBadge status={job.status} />
                  <span className="text-sm font-semibold text-slate-800">{job.task_id}</span>
                  <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded">{job.mode}</span>
                  <span className="text-xs text-slate-400 font-mono">{job.id.substring(0, 8)}</span>
                </div>
                <div className="flex items-center gap-3">
                  {job.started_at && (
                    <span className="text-xs text-slate-500">{new Date(job.started_at).toLocaleTimeString()}</span>
                  )}
                  {(job.status === 'running' || job.status === 'pending') && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleCancelJob(job.id)
                      }}
                      disabled={cancelLoading === job.id}
                      className="px-2.5 py-1 text-xs text-red-600 hover:text-red-800 font-medium border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50 flex items-center gap-1 transition-colors"
                    >
                      {cancelLoading === job.id && <LoadingSpinner size="sm" />}
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
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
          {/* View toggle */}
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
                {history.map((entry, idx) => {
                  const duration =
                    entry.started_at && entry.finished_at
                      ? Math.round(
                          (new Date(entry.finished_at).getTime() - new Date(entry.started_at).getTime()) / 1000
                        )
                      : null
                  const durationStr =
                    duration !== null
                      ? duration >= 60
                        ? `${Math.floor(duration / 60)}m ${duration % 60}s`
                        : `${duration}s`
                      : '-'
                  return (
                    <tr
                      key={entry.id}
                      className={`hover:bg-slate-50 transition-colors ${
                        idx !== history.length - 1 ? 'border-b border-slate-100' : ''
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
          </div>
        )}
      </div>
    </div>
  )
}
