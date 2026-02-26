import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import type { TaskDetail as TaskDetailType, AnalysisMode, ChatSession, ProgressEvent } from '../types'
import type { WSMessage } from '../hooks/useWebSocket'
import { api } from '../api/client'
import { useAnalysisStore } from '../stores/analysisStore'
import { useToastStore } from '../stores/toastStore'
import { useWebSocket } from '../hooks/useWebSocket'
import StatusBadge from '../components/StatusBadge'
import MarkdownViewer from '../components/MarkdownViewer'
import ChatPanel from '../components/ChatPanel'
import ProgressBanner from '../components/ProgressBanner'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'
import EmptyState from '../components/ui/EmptyState'
import TaskSidebar from '../components/task-detail/TaskSidebar'
import DescriptionTab from '../components/task-detail/DescriptionTab'
import CommentsTab from '../components/task-detail/CommentsTab'

type TabKey = 'issue' | 'report' | 'review' | 'comments'
type ReviewSubTab = 'patch_review' | 'patch_diff'
type DebugView = 'context' | 'raw' | null

const TABS: { key: TabKey; label: string }[] = [
  { key: 'issue', label: 'Issue' },
  { key: 'report', label: 'Report' },
  { key: 'review', label: 'Review' },
  { key: 'comments', label: 'Comments' },
]

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<TaskDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('issue')
  const [reviewSubTab, setReviewSubTab] = useState<ReviewSubTab>('patch_review')
  const [debugView, setDebugView] = useState<DebugView>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [analyzeOpen, setAnalyzeOpen] = useState(false)
  const [assigneesExpanded, setAssigneesExpanded] = useState(false)
  const [jobElapsed, setJobElapsed] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [chatOpen, setChatOpen] = useState(false)

  const { addToast } = useToastStore()

  const { jobs, progressEvents, fetchJobs, addOutputLine, addProgressEvent, updateJob, updateJobMode } =
    useAnalysisStore()

  const activeJob = useMemo(
    () => jobs.find((j) => j.task_id === id && (j.status === 'running' || j.status === 'pending')) ?? null,
    [jobs, id]
  )

  const latestJob = useMemo(
    () => activeJob ?? jobs.find((j) => j.task_id === id) ?? null,
    [jobs, id, activeJob]
  )

  const loadTask = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [result, sessionsResult] = await Promise.all([
        api.getTask(id),
        api.chatSessions(id).catch(() => ({ sessions: [] })),
      ])
      setTask(result)
      setChatSessions(sessionsResult.sessions)
      if (result.report_content) {
        setActiveTab('report')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load task')
    } finally {
      setLoading(false)
    }
  }, [id])

  const loadTaskRef = useRef(loadTask)
  useEffect(() => { loadTaskRef.current = loadTask }, [loadTask])

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
          loadTaskRef.current()
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
    fetchJobs()
  }, [loadTask, fetchJobs])

  useEffect(() => {
    if (!activeJob) return
    const interval = setInterval(() => fetchJobs(), 5000)
    return () => clearInterval(interval)
  }, [activeJob, fetchJobs])

  useEffect(() => {
    if (!analyzeOpen) return
    const handler = () => setAnalyzeOpen(false)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [analyzeOpen])

  useEffect(() => {
    if (activeJob?.status === 'running' && activeJob.started_at) {
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
    try {
      const result = await fn() as Record<string, unknown> | undefined
      const status = result?.status as string | undefined
      const message = (result?.message as string) || `${actionName} completed`
      if (status === 'no_docs' || status === 'no_patches') {
        addToast({ type: 'warning', title: actionName, message })
      } else if (status === 'error') {
        addToast({ type: 'error', title: actionName, message })
      } else {
        addToast({ type: 'success', title: actionName, message })
        loadTask()
      }
    } catch (e) {
      addToast({ type: 'error', title: actionName, message: e instanceof Error ? e.message : `${actionName} failed` })
    } finally {
      setActionLoading(null)
    }
  }

  const handleAnalyze = async (mode: AnalysisMode) => {
    if (!id) return
    setAnalyzeOpen(false)
    setActionLoading(`Analyze (${mode})`)
    try {
      const result = await api.startAnalysis(id, mode)
      if ((result as unknown as Record<string, unknown>).status === 'error') {
        const msg = (result as unknown as Record<string, unknown>).message as string
        addToast({ type: 'error', title: 'Analysis', message: msg || 'Analysis failed to start' })
        setActionLoading(null)
        return
      }
      updateJob(result)
      addToast({ type: 'success', title: 'Analysis started', message: `Mode: ${mode}` })
      setActionLoading(null)
    } catch (e) {
      addToast({ type: 'error', title: 'Analysis', message: e instanceof Error ? e.message : 'Failed to start analysis' })
      setActionLoading(null)
    }
  }

  const handleCancelJob = async () => {
    if (!activeJob) return
    try {
      await api.cancelJob(activeJob.id)
      await fetchJobs()
      addToast({ type: 'warning', title: 'Analysis cancelled' })
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

  const jobProgress = latestJob
    ? (progressEvents[latestJob.id]?.length ? progressEvents[latestJob.id] : latestJob.progress_events || [])
    : []

  const tabHasContent = (key: TabKey): boolean => {
    switch (key) {
      case 'issue': return !!(task.markdown_description || task.description)
      case 'report': return !!task.report_content
      case 'review': return !!(task.patch_review_content || task.patch_diff_content)
      case 'comments': return task.comments.length > 0
    }
  }

  const handleTabChange = (tab: string) => {
    if (tab === 'report' || tab === 'review' || tab === 'comments' || tab === 'issue') {
      setDebugView(null)
      setActiveTab(tab as TabKey)
    } else if (tab === 'context' || tab === 'raw') {
      setDebugView(tab as DebugView)
    } else if (tab === 'patch_review' || tab === 'patch_diff') {
      setDebugView(null)
      setActiveTab('review')
      setReviewSubTab(tab as ReviewSubTab)
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

      <div className="flex gap-5">
        {/* Sidebar */}
        <TaskSidebar
          task={task}
          analyzeOpen={analyzeOpen}
          setAnalyzeOpen={setAnalyzeOpen}
          assigneesExpanded={assigneesExpanded}
          setAssigneesExpanded={setAssigneesExpanded}
          actionLoading={actionLoading}
          onAnalyze={handleAnalyze}
          onCancelJob={handleCancelJob}
          onAction={runAction}
          onTabChange={handleTabChange}
          api={api}
        />

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          {/* Progress Banner */}
          {latestJob && (
            <ProgressBanner
              job={latestJob}
              elapsed={jobElapsed}
              progress={jobProgress}
              onCancel={handleCancelJob}
              onViewReport={task.report_content ? () => { setActiveTab('report'); setDebugView(null) } : undefined}
            />
          )}

          {/* Tab Bar */}
          <div className="bg-white rounded-t-xl border border-slate-200 border-b-0 px-2 pt-2">
            <nav className="flex gap-0.5 overflow-x-auto">
              {TABS.map((tab) => {
                const hasContent = tabHasContent(tab.key)
                const isActive = activeTab === tab.key && !debugView
                return (
                  <button
                    key={tab.key}
                    onClick={() => { setActiveTab(tab.key); setDebugView(null) }}
                    className={`whitespace-nowrap px-3.5 py-2.5 text-sm font-medium rounded-t-lg transition-colors relative ${
                      isActive
                        ? 'bg-slate-50 text-blue-700 border border-slate-200 border-b-white -mb-px z-10'
                        : hasContent
                          ? 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
                          : 'text-slate-300'
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      {hasContent && (
                        <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-blue-500' : 'bg-emerald-400'}`} />
                      )}
                      {tab.label}
                    </span>
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
            {debugView === 'context' ? (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded">Debug: Context</span>
                  <button onClick={() => setDebugView(null)} className="text-xs text-slate-400 hover:text-slate-600">Close</button>
                </div>
                {task.context_content ? <MarkdownViewer content={task.context_content} /> : <EmptyState text="No context file available" />}
              </div>
            ) : debugView === 'raw' ? (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded">Debug: Raw JSON</span>
                  <button onClick={() => setDebugView(null)} className="text-xs text-slate-400 hover:text-slate-600">Close</button>
                </div>
                <pre className="text-xs font-mono bg-slate-50 text-slate-700 p-4 rounded-lg overflow-auto max-h-[700px] border border-slate-200 leading-relaxed">
                  {JSON.stringify(task, null, 2)}
                </pre>
              </div>
            ) : (
              <>
                {activeTab === 'issue' && <DescriptionTab task={task} />}

                {activeTab === 'report' && (
                  task.report_content
                    ? <MarkdownViewer content={task.report_content} />
                    : <EmptyState text="No report yet" action={{ label: 'Run Analysis', onClick: () => setAnalyzeOpen(true) }} />
                )}

                {activeTab === 'review' && (
                  <div>
                    <div className="flex items-center gap-1 mb-4 bg-slate-100 rounded-lg p-0.5 w-fit">
                      <button
                        onClick={() => setReviewSubTab('patch_review')}
                        className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                          reviewSubTab === 'patch_review'
                            ? 'bg-white text-slate-800 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                        }`}
                      >
                        Patch Review
                      </button>
                      <button
                        onClick={() => setReviewSubTab('patch_diff')}
                        className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                          reviewSubTab === 'patch_diff'
                            ? 'bg-white text-slate-800 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                        }`}
                      >
                        Patch Diff
                      </button>
                    </div>
                    {reviewSubTab === 'patch_review' ? (
                      task.patch_review_content
                        ? <MarkdownViewer content={task.patch_review_content} />
                        : <EmptyState text="Run QA Review to generate." />
                    ) : (
                      task.patch_diff_content
                        ? <MarkdownViewer content={task.patch_diff_content} />
                        : <EmptyState text="No patch diff available" />
                    )}
                  </div>
                )}

                {activeTab === 'comments' && (
                  task.comments.length > 0
                    ? <CommentsTab comments={task.comments} />
                    : <EmptyState text="Comments sync on task fetch." action={{ label: 'Fetch Task', onClick: () => runAction('Fetch Task', () => api.fetchTask(task.id)) }} />
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Chat slide-over panel */}
      <ChatPanel
        taskId={task.id}
        sessions={chatSessions}
        onSessionCreated={() => {
          api.chatSessions(task.id).then(r => setChatSessions(r.sessions)).catch(() => {})
        }}
        open={chatOpen}
        onClose={() => setChatOpen(false)}
      />

      {/* Floating Ask AI button */}
      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-6 right-6 w-12 h-12 bg-gradient-to-br from-violet-500 to-purple-600 text-white rounded-full shadow-lg hover:shadow-xl flex items-center justify-center transition-all hover:scale-105 z-30"
          title="Ask AI"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      )}
    </div>
  )
}
