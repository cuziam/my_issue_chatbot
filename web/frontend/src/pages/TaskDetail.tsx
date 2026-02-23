import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import type { TaskDetail as TaskDetailType, AnalysisMode } from '../types'
import type { WSMessage } from '../hooks/useWebSocket'
import { api } from '../api/client'
import { useAnalysisStore } from '../stores/analysisStore'
import { useWebSocket } from '../hooks/useWebSocket'
import StatusBadge from '../components/StatusBadge'
import MarkdownViewer from '../components/MarkdownViewer'
import ProgressTimeline from '../components/ProgressTimeline'
import AnalysisLog from '../components/AnalysisLog'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'

type TabKey = 'description' | 'report' | 'patch_review' | 'patch_diff' | 'context' | 'comments' | 'progress' | 'raw'
type LogView = 'progress' | 'raw'

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'description', label: 'Description', icon: '\uD83D\uDCC4' },
  { key: 'report', label: 'Report', icon: '\uD83D\uDCCB' },
  { key: 'patch_review', label: 'Patch Review', icon: '\uD83D\uDD0D' },
  { key: 'patch_diff', label: 'Patch Diff', icon: '\u2194\uFE0F' },
  { key: 'context', label: 'Context', icon: '\uD83D\uDCC2' },
  { key: 'comments', label: 'Comments', icon: '\uD83D\uDCAC' },
  { key: 'progress', label: 'Progress', icon: '\u25B6' },
  { key: 'raw', label: 'Raw JSON', icon: '{ }' },
]

const ANALYSIS_MODES: { value: AnalysisMode; label: string; desc: string }[] = [
  { value: 'initial', label: 'Initial Analysis', desc: 'Researcher + Analyzer team으로 이슈 최초 분석 → report.md 생성' },
  { value: 'review', label: 'QA Review', desc: '개발자 수정 후 검증. 패치 있으면 자동 패치 리뷰, 없으면 verification 수행' },
  { value: 'activity_update', label: 'Activity Update', desc: '새 댓글/본문 변경 감지 후 팔로업. report.md에 추가 분석 append' },
]

function attachmentToUrl(path: string): string {
  const tasksIndex = path.replace(/\\/g, '/').indexOf('tasks/')
  if (tasksIndex === -1) return path
  return '/files/' + path.replace(/\\/g, '/').substring(tasksIndex)
}

function isImageFile(name: string): boolean {
  return /\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i.test(name)
}

function formatDate(dateStr: string): string {
  const ts = Number(dateStr)
  if (!isNaN(ts) && ts > 1e12) {
    return new Date(ts).toLocaleString('ko-KR')
  }
  return new Date(dateStr).toLocaleString('ko-KR')
}

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<TaskDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('description')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'warning' | 'error'; text: string } | null>(null)
  const [analyzeOpen, setAnalyzeOpen] = useState(false)
  const [assigneesExpanded, setAssigneesExpanded] = useState(false)
  const [jobElapsed, setJobElapsed] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [logView, setLogView] = useState<LogView>('progress')

  // Global store for jobs + progress
  const { jobs, activeJobOutput, progressEvents, fetchJobs, addOutputLine, addProgressEvent, updateJob, updateJobMode } =
    useAnalysisStore()

  // Derive activeJob from global store: running/pending job for this task
  const activeJob = useMemo(
    () => jobs.find((j) => j.task_id === id && (j.status === 'running' || j.status === 'pending')) ?? null,
    [jobs, id]
  )

  // Also find the most recent completed job for this task (for progress tab after completion)
  const latestJob = useMemo(
    () => activeJob ?? jobs.find((j) => j.task_id === id) ?? null,
    [jobs, id, activeJob]
  )

  const loadTask = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.getTask(id)
      setTask(result)
      // Auto-select report tab if report exists and description is empty
      if (result.report_content && !result.markdown_description && !result.description) {
        setActiveTab('report')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load task')
    } finally {
      setLoading(false)
    }
  }, [id])

  // Ref to avoid stale closure in WS handler
  const loadTaskRef = useRef(loadTask)
  useEffect(() => { loadTaskRef.current = loadTask }, [loadTask])

  // WebSocket handler — same pattern as Analysis.tsx
  const handleWsMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case 'job_started':
          updateJob(msg.job)
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
          loadTaskRef.current() // refresh artifacts (report, patch_review, etc.)
          break
        case 'mode_resolved':
          updateJobMode(msg.job_id, msg.resolved_mode)
          break
      }
    },
    [updateJob, updateJobMode, addOutputLine, addProgressEvent]
  )

  useWebSocket(handleWsMessage)

  useEffect(() => {
    loadTask()
    // Fetch global jobs to restore any running job for this task
    fetchJobs()
  }, [loadTask, fetchJobs])

  // Fallback polling: refresh jobs every 5s while a job is running for this task
  useEffect(() => {
    if (!activeJob) return
    const interval = setInterval(() => fetchJobs(), 5000)
    return () => clearInterval(interval)
  }, [activeJob, fetchJobs])

  // Close dropdown on outside click
  useEffect(() => {
    if (!analyzeOpen) return
    const handler = () => setAnalyzeOpen(false)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [analyzeOpen])

  // Elapsed timer for running job
  useEffect(() => {
    if (activeJob?.status === 'running' && activeJob.started_at) {
      // Initialize elapsed from started_at
      setJobElapsed(Math.floor((Date.now() - new Date(activeJob.started_at).getTime()) / 1000))
      timerRef.current = setInterval(() => setJobElapsed((e) => e + 1), 1000)
      return () => {
        if (timerRef.current) clearInterval(timerRef.current)
      }
    } else {
      setJobElapsed(0)
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    }
  }, [activeJob?.id, activeJob?.status, activeJob?.started_at])

  const runAction = async (actionName: string, fn: () => Promise<unknown>) => {
    setActionLoading(actionName)
    setActionMessage(null)
    try {
      const result = await fn() as Record<string, unknown> | undefined
      const status = result?.status as string | undefined
      const message = (result?.message as string) || `${actionName} completed`
      if (status === 'no_docs' || status === 'no_patches') {
        setActionMessage({ type: 'warning', text: message })
      } else if (status === 'error') {
        setActionMessage({ type: 'error', text: message })
      } else {
        setActionMessage({ type: 'success', text: message })
        loadTask()
      }
    } catch (e) {
      setActionMessage({ type: 'error', text: e instanceof Error ? e.message : `${actionName} failed` })
    } finally {
      setActionLoading(null)
    }
  }

  const handleAnalyze = async (mode: AnalysisMode) => {
    if (!id) return
    setAnalyzeOpen(false)
    setActionLoading(`Analyze (${mode})`)
    setActionMessage(null)
    try {
      const result = await api.startAnalysis(id, mode)
      // Pre-validation error (no job spawned)
      if ((result as unknown as Record<string, unknown>).status === 'error') {
        const msg = (result as unknown as Record<string, unknown>).message as string
        setActionMessage({ type: 'error', text: msg || 'Analysis failed to start' })
        setActionLoading(null)
        return
      }
      // Job started — store will pick it up via WebSocket + fallback polling
      updateJob(result)
      setActionMessage({ type: 'success', text: `Analysis started (${mode})` })
      setActionLoading(null)
      setActiveTab('progress')
    } catch (e) {
      setActionMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to start analysis' })
      setActionLoading(null)
    }
  }

  const handleCancelJob = async () => {
    if (!activeJob) return
    try {
      await api.cancelJob(activeJob.id)
      await fetchJobs()
      setActionMessage({ type: 'warning', text: 'Analysis cancelled' })
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) return <ErrorMessage message={error} onRetry={loadTask} />
  if (!task) return <ErrorMessage message="Task not found" />

  const visibleAssignees = assigneesExpanded ? task.assignees : task.assignees.slice(0, 3)
  const hasMoreAssignees = task.assignees.length > 3
  const versionFields = Object.entries(task.custom_fields).filter(([k]) => k.toLowerCase().includes('version'))
  const otherFields = Object.entries(task.custom_fields).filter(([k]) => !k.toLowerCase().includes('version'))

  const jobProgress = latestJob ? progressEvents[latestJob.id] || [] : []
  const jobOutput = latestJob ? activeJobOutput[latestJob.id] || [] : []
  const isJobRunning = activeJob?.status === 'running'

  const tabHasContent = (key: TabKey): boolean => {
    switch (key) {
      case 'description': return !!(task.markdown_description || task.description)
      case 'report': return !!task.report_content
      case 'patch_review': return !!task.patch_review_content
      case 'patch_diff': return !!task.patch_diff_content
      case 'context': return !!task.context_content
      case 'comments': return task.comments.length > 0
      case 'progress': return !!latestJob
      case 'raw': return true
    }
  }

  return (
    <div>
      {/* Breadcrumb + Header */}
      <div className="mb-5">
        <Link to="/" className="text-blue-600 hover:text-blue-800 text-sm inline-flex items-center gap-1 mb-3">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          Dashboard
        </Link>
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-slate-900 leading-tight">
              <span className="text-blue-600">{task.id}</span>
              <span className="text-slate-300 mx-2">|</span>
              {task.name}
            </h1>
            <div className="mt-2 flex items-center gap-3 flex-wrap">
              <StatusBadge status={task.status} />
              {task.url && (
                <a href={task.url} target="_blank" rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:text-blue-800 inline-flex items-center gap-1">
                  Open in ClickUp
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                </a>
              )}
              {task.tags.map((tag) => (
                <span key={tag} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Action message */}
      {actionMessage && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm flex items-center gap-2 ${
          actionMessage.type === 'success'
            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
            : actionMessage.type === 'warning'
              ? 'bg-amber-50 text-amber-800 border border-amber-200'
              : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          <span>{actionMessage.type === 'success' ? '\u2713' : actionMessage.type === 'warning' ? '\u26A0' : '\u2717'}</span>
          {actionMessage.text}
        </div>
      )}

      <div className="flex gap-5">
        {/* Sidebar */}
        <div className="w-64 flex-shrink-0 space-y-4">
          {/* Version Info */}
          {versionFields.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Versions</h3>
              <dl className="space-y-2">
                {versionFields.map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs text-slate-500">{key}</dt>
                    <dd className="text-sm font-mono text-slate-800 mt-0.5">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Assignees */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Assignees
              {task.assignees.length > 0 && (
                <span className="text-slate-300 font-normal ml-1">({task.assignees.length})</span>
              )}
            </h3>
            {task.assignees.length === 0 ? (
              <p className="text-sm text-slate-400 italic">None</p>
            ) : (
              <div>
                <div className="space-y-1.5">
                  {visibleAssignees.map((a, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center flex-shrink-0">
                        <span className="text-white text-[10px] font-medium">{a.charAt(0).toUpperCase()}</span>
                      </div>
                      <span className="text-sm text-slate-700 truncate">{a}</span>
                    </div>
                  ))}
                </div>
                {hasMoreAssignees && (
                  <button
                    onClick={() => setAssigneesExpanded(!assigneesExpanded)}
                    className="mt-2 text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {assigneesExpanded ? 'Show less' : `+${task.assignees.length - 3} more...`}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Other Custom Fields */}
          {otherFields.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Fields</h3>
              <dl className="space-y-2">
                {otherFields.map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs text-slate-500">{key}</dt>
                    <dd className="text-sm text-slate-800 mt-0.5">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Artifacts */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Artifacts</h3>
            <ul className="space-y-2">
              {[
                { label: 'Report', has: task.has_report, tab: 'report' as TabKey },
                { label: 'Patch Review', has: task.has_patch_review, tab: 'patch_review' as TabKey },
                { label: 'Context', has: task.has_context, tab: 'context' as TabKey },
                { label: 'Patch Diff', has: !!task.patch_diff_content, tab: 'patch_diff' as TabKey },
              ].map((item) => (
                <li key={item.label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${item.has ? 'bg-emerald-500' : 'bg-slate-200'}`} />
                    <span className={`text-sm ${item.has ? 'text-slate-700' : 'text-slate-400'}`}>{item.label}</span>
                  </div>
                  {item.has && (
                    <button onClick={() => setActiveTab(item.tab)} className="text-xs text-blue-600 hover:text-blue-800">View</button>
                  )}
                </li>
              ))}
            </ul>
          </div>

          {/* Actions */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Actions</h3>
            <div className="space-y-2">
              {/* Active Job Progress Banner */}
              {activeJob && activeJob.status === 'running' && (
                <div className="px-3 py-2.5 bg-blue-50 border border-blue-200 rounded-lg text-sm">
                  <div className="flex items-center gap-2 text-blue-800 font-medium">
                    <LoadingSpinner size="sm" />
                    Analysis in progress
                  </div>
                  <div className="text-xs text-blue-600 mt-1">
                    {activeJob.mode} &middot; {Math.floor(jobElapsed / 60)}m {jobElapsed % 60}s
                  </div>
                  <div className="flex items-center gap-3 mt-2">
                    <button onClick={() => setActiveTab('progress')} className="text-xs text-blue-600 hover:text-blue-800 font-medium">
                      View Progress
                    </button>
                    <button onClick={handleCancelJob} className="text-xs text-red-600 hover:text-red-800 font-medium">
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              {/* Analyze Button */}
              <div className="relative" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => setAnalyzeOpen(!analyzeOpen)}
                  disabled={actionLoading !== null}
                  className="w-full px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2 transition-colors shadow-sm"
                >
                  {actionLoading?.startsWith('Analyze') && <LoadingSpinner size="sm" />}
                  Analyze
                  <svg className={`w-3.5 h-3.5 transition-transform ${analyzeOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </button>
                {analyzeOpen && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-10 overflow-hidden">
                    {ANALYSIS_MODES.map((mode) => (
                      <button
                        key={mode.value}
                        onClick={() => handleAnalyze(mode.value)}
                        className="w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-100 last:border-0 transition-colors"
                      >
                        <div className="text-sm font-medium text-slate-800">{mode.label}</div>
                        <div className="text-xs text-slate-400 mt-0.5">{mode.desc}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {/* Other Actions */}
              {[
                { name: 'Fetch Task', fn: () => api.fetchTask(task.id) },
                { name: 'Fetch Doc', fn: () => api.fetchDoc(task.id) },
                { name: 'Generate Diff', fn: () => api.generateDiff(task.id) },
              ].map((action) => (
                <button
                  key={action.name}
                  onClick={() => runAction(action.name, action.fn)}
                  disabled={actionLoading !== null}
                  className="w-full px-3 py-2 bg-white text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50 hover:border-slate-300 text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
                >
                  {actionLoading === action.name && <LoadingSpinner size="sm" />}
                  {action.name}
                </button>
              ))}
            </div>
          </div>

          {/* Attachments */}
          {task.attachments.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Attachments ({task.attachments.length})
              </h3>
              <ul className="space-y-2">
                {task.attachments.map((att, idx) => (
                  <li key={idx}>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 uppercase font-mono">{att.type}</span>
                      <span className="text-sm text-slate-700 truncate" title={att.original_name}>{att.original_name}</span>
                    </div>
                    {att.extracted_files && att.extracted_files.length > 0 && (
                      <ul className="ml-6 mt-1 space-y-0.5">
                        {att.extracted_files.slice(0, 5).map((f, fi) => (
                          <li key={fi} className="text-xs text-slate-400 truncate">{f.name}</li>
                        ))}
                        {att.extracted_files.length > 5 && (
                          <li className="text-xs text-slate-400">...+{att.extracted_files.length - 5} more</li>
                        )}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          {/* Tab Bar */}
          <div className="bg-white rounded-t-xl border border-slate-200 border-b-0 px-2 pt-2">
            <nav className="flex gap-0.5 overflow-x-auto">
              {TABS.map((tab) => {
                const hasContent = tabHasContent(tab.key)
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`whitespace-nowrap px-3.5 py-2.5 text-sm font-medium rounded-t-lg transition-colors relative ${
                      activeTab === tab.key
                        ? 'bg-slate-50 text-blue-700 border border-slate-200 border-b-white -mb-px z-10'
                        : hasContent
                          ? 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
                          : 'text-slate-300'
                    }`}
                  >
                    {tab.label}
                    {tab.key === 'progress' && isJobRunning && (
                      <span className="ml-1.5 inline-flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                        <span className="text-[10px] text-blue-600 font-semibold">live</span>
                      </span>
                    )}
                    {tab.key === 'comments' && task.comments.length > 0 && (
                      <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-600">{task.comments.length}</span>
                    )}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="bg-white rounded-b-xl rounded-tr-xl border border-slate-200 p-6 min-h-[400px]">
            {activeTab === 'description' && (
              <div>
                {task.markdown_description ? (
                  <MarkdownViewer content={task.markdown_description} />
                ) : task.description ? (
                  <pre className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed">{task.description}</pre>
                ) : (
                  <EmptyState text="No description available" />
                )}

                {/* Inline Images */}
                {task.attachments.filter((a) => isImageFile(a.original_name)).length > 0 && (
                  <div className="mt-8 pt-6 border-t border-slate-200">
                    <h4 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                      <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      Attached Images
                    </h4>
                    <div className="grid gap-4">
                      {task.attachments
                        .filter((a) => isImageFile(a.original_name))
                        .map((att, idx) => (
                          <div key={idx} className="group">
                            <p className="text-xs text-slate-400 mb-1.5">{att.original_name}</p>
                            <img
                              src={attachmentToUrl(att.path)}
                              alt={att.original_name}
                              className="max-w-full rounded-lg border border-slate-200 shadow-sm group-hover:shadow-md transition-shadow"
                              loading="lazy"
                            />
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'report' && (
              task.report_content ? <MarkdownViewer content={task.report_content} /> : <EmptyState text="No report generated yet" />
            )}

            {activeTab === 'patch_review' && (
              task.patch_review_content ? <MarkdownViewer content={task.patch_review_content} /> : <EmptyState text="No patch review available" />
            )}

            {activeTab === 'patch_diff' && (
              task.patch_diff_content ? <MarkdownViewer content={task.patch_diff_content} /> : <EmptyState text="No patch diff available" />
            )}

            {activeTab === 'context' && (
              task.context_content ? <MarkdownViewer content={task.context_content} /> : <EmptyState text="No context file available" />
            )}

            {activeTab === 'comments' && (
              task.comments.length === 0 ? (
                <EmptyState text="No comments" />
              ) : (
                <div className="space-y-0">
                  {task.comments.map((comment, idx) => (
                    <div key={idx} className={`py-4 ${idx > 0 ? 'border-t border-slate-100' : ''}`}>
                      <div className="flex items-center gap-2.5 mb-2">
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-slate-400 to-slate-600 flex items-center justify-center flex-shrink-0">
                          <span className="text-white text-[10px] font-medium">{comment.user?.charAt(0)?.toUpperCase() || '?'}</span>
                        </div>
                        <span className="text-sm font-medium text-slate-800">{comment.user}</span>
                        <span className="text-xs text-slate-400">{formatDate(comment.date)}</span>
                      </div>
                      <div className="ml-9.5 text-sm text-slate-600 leading-relaxed whitespace-pre-wrap pl-[38px]">{comment.comment}</div>
                    </div>
                  ))}
                </div>
              )
            )}

            {activeTab === 'progress' && (
              latestJob ? (
                <div>
                  {/* View toggle */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-slate-800">
                        {isJobRunning ? 'Live Progress' : `Job ${latestJob.status}`}
                      </h3>
                      <span className="text-xs text-slate-400 font-mono bg-slate-100 px-2 py-0.5 rounded">
                        {latestJob.mode} &middot; {latestJob.id.substring(0, 8)}
                      </span>
                      {isJobRunning && (
                        <span className="inline-flex items-center gap-1 text-xs text-blue-600">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                          {Math.floor(jobElapsed / 60)}m {jobElapsed % 60}s
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
                    <ProgressTimeline events={jobProgress} isRunning={isJobRunning} />
                  ) : (
                    <AnalysisLog lines={jobOutput} />
                  )}
                </div>
              ) : (
                <EmptyState text="No analysis job for this task" />
              )
            )}

            {activeTab === 'raw' && (
              <pre className="text-xs font-mono bg-slate-50 text-slate-700 p-4 rounded-lg overflow-auto max-h-[700px] border border-slate-200 leading-relaxed">
                {JSON.stringify(task, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-slate-400">
      <svg className="w-12 h-12 mb-3 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p className="text-sm italic">{text}</p>
    </div>
  )
}
