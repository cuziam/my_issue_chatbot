import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from '../../api/client'
import { useWebSocketContext } from '../../contexts/WebSocketContext'
import type { DigestSummary, DigestDetail, DigestJob, ProgressEvent } from '../../types'
import MarkdownViewer from '../../components/MarkdownViewer'
import ProgressTimeline from '../../components/ProgressTimeline'
import LoadingSpinner from '../../components/LoadingSpinner'

function formatDate(d: string) {
  try {
    return new Date(d).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
  } catch {
    return d
  }
}

function ElapsedTime({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const start = new Date(startedAt).getTime()
    const update = () => setElapsed(Math.floor((Date.now() - start) / 1000))
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [startedAt])
  const m = Math.floor(elapsed / 60)
  const s = elapsed % 60
  return <span className="font-mono text-xs text-slate-500">{m}:{s.toString().padStart(2, '0')}</span>
}

function SeverityBadges({ counts }: { counts: Record<string, number> }) {
  const badges = [
    { key: 'critical', label: 'C', color: 'bg-red-100 text-red-700' },
    { key: 'high', label: 'H', color: 'bg-orange-100 text-orange-700' },
    { key: 'medium', label: 'M', color: 'bg-yellow-100 text-yellow-700' },
    { key: 'low', label: 'L', color: 'bg-green-100 text-green-700' },
    { key: 'info', label: 'I', color: 'bg-blue-100 text-blue-700' },
  ]
  return (
    <div className="flex gap-1">
      {badges.map(b => {
        const n = counts[b.key] || 0
        if (n === 0) return null
        return (
          <span key={b.key} className={`px-1.5 py-0.5 rounded text-xs font-medium ${b.color}`}>
            {b.label}:{n}
          </span>
        )
      })}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    error: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-slate-100 text-slate-600'}`}>
      {status}
    </span>
  )
}

export default function Digests() {
  const [digests, setDigests] = useState<DigestSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDigest, setSelectedDigest] = useState<DigestDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Active job tracking
  const [activeJob, setActiveJob] = useState<DigestJob | null>(null)
  const [progressEvents, setProgressEvents] = useState<ProgressEvent[]>([])
  const activeJobIdRef = useRef<string | null>(null)

  // Generate form
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - d.getDay() + 1) // Monday
    return d.toISOString().split('T')[0]
  })
  const [dateTo, setDateTo] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - d.getDay() + 5) // Friday
    return d.toISOString().split('T')[0]
  })

  // Edit mode
  const [editMode, setEditMode] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)

  const { lastMessage } = useWebSocketContext()

  const loadDigests = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getDigests()
      setDigests(data.digests)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (id: string) => {
    setLoadingDetail(true)
    setEditMode(false)
    try {
      const data = await api.getDigest(id)
      setSelectedDigest(data)
      setEditContent(data.content)
    } catch {
      // ignore
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  // On mount: load digests + check for running jobs
  useEffect(() => {
    loadDigests()

    // Check if there's already a running digest job
    api.getDigestJobs().then(data => {
      const running = data.jobs.find(j => j.status === 'running')
      if (running) {
        setActiveJob(running)
        activeJobIdRef.current = running.id
        setProgressEvents(
          (running.progress_events || []).map(e => ({
            event: e.event as ProgressEvent['event'],
            detail: e.detail,
            timestamp: (e as Record<string, unknown>).timestamp as string | undefined,
          }))
        )
      }
    }).catch(() => {})
  }, [loadDigests])

  // Polling: while job is running, poll every 5s to stay in sync
  useEffect(() => {
    if (!activeJob || activeJob.status !== 'running') return
    const timer = setInterval(async () => {
      try {
        const job = await api.getDigestJob(activeJob.id)
        setActiveJob(job)
        if (job.progress_events) {
          setProgressEvents(
            job.progress_events.map(e => ({
              event: e.event as ProgressEvent['event'],
              detail: e.detail,
              timestamp: (e as Record<string, unknown>).timestamp as string | undefined,
            }))
          )
        }
        if (job.status !== 'running') {
          if (job.status === 'completed' && job.digest_id) {
            loadDigests()
            loadDetail(job.digest_id)
          }
        }
      } catch {
        // ignore
      }
    }, 5000)
    return () => clearInterval(timer)
  }, [activeJob, loadDigests, loadDetail])

  // WebSocket: real-time progress events
  useEffect(() => {
    if (!lastMessage) return
    try {
      const msg = JSON.parse(lastMessage)
      if (msg.type === 'digest_progress' && msg.job_id === activeJobIdRef.current) {
        const evt: ProgressEvent = {
          event: msg.event || 'text',
          tool: msg.tool,
          detail: msg.detail,
          timestamp: msg.timestamp,
          duration_ms: msg.duration_ms,
          num_turns: msg.num_turns,
          cost_usd: msg.cost_usd,
          subtype: msg.subtype,
        }
        setProgressEvents(prev => [...prev, evt])
      } else if (msg.type === 'digest_completed') {
        const job = msg.job as DigestJob
        setActiveJob(job)
        if (job.status === 'completed' && job.digest_id) {
          loadDigests()
          loadDetail(job.digest_id)
        }
      } else if (msg.type === 'digest_started') {
        const job = msg.job as DigestJob
        setActiveJob(job)
        activeJobIdRef.current = job.id
        setProgressEvents([])
      }
    } catch {
      // ignore
    }
  }, [lastMessage, loadDigests, loadDetail])

  const handleGenerate = async () => {
    setSelectedDigest(null)
    setProgressEvents([])
    try {
      const result = await api.generateDigest(dateFrom, dateTo)
      if (result.status === 'error') {
        setActiveJob({ ...result, finished_at: null, digest_id: null, progress_events: [] } as DigestJob)
      } else {
        setActiveJob(result)
        activeJobIdRef.current = result.id
      }
    } catch {
      // ignore
    }
  }

  const handleSave = async () => {
    if (!selectedDigest) return
    setSaving(true)
    try {
      const updated = await api.updateDigest(selectedDigest.id, editContent)
      setSelectedDigest(updated)
      setEditMode(false)
      loadDigests()
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }

  const handleCopyMd = () => {
    const content = editMode ? editContent : (selectedDigest?.content || '')
    navigator.clipboard.writeText(content)
  }

  const handleDownloadHtml = () => {
    if (!selectedDigest) return
    const content = editMode ? editContent : selectedDigest.content
    const html = buildHtmlDownload(selectedDigest.id, content)
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedDigest.id}.html`
    a.click()
    URL.revokeObjectURL(url)
  }

  const isJobRunning = activeJob?.status === 'running'
  const isJobDone = activeJob && activeJob.status !== 'running'
  const showProgress = isJobRunning || (isJobDone && !selectedDigest)

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-800">Weekly Digest</h1>
        <p className="text-sm text-slate-500 mt-0.5">Generate and manage weekly issue digests for field engineers</p>
      </div>

      {/* Generate Form */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 mb-6">
        <div className="flex items-center gap-3 flex-wrap">
          <label className="text-sm font-medium text-slate-600">Date Range:</label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            disabled={isJobRunning}
          />
          <span className="text-slate-400">~</span>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            disabled={isJobRunning}
          />
          <button
            onClick={handleGenerate}
            disabled={isJobRunning}
            className="px-4 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isJobRunning ? 'Generating...' : 'Generate'}
          </button>
          {isJobRunning && activeJob && (
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              <ElapsedTime startedAt={activeJob.started_at} />
            </div>
          )}
        </div>
      </div>

      {/* Active Job Status Bar */}
      {activeJob && activeJob.status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-6 flex items-center gap-2">
          <StatusBadge status="failed" />
          <span className="text-sm text-red-700">{activeJob.error || 'Generation failed'}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Digest List */}
        <div className="lg:col-span-1">
          <h2 className="text-sm font-semibold text-slate-600 mb-3 uppercase tracking-wide">History</h2>
          {loading ? (
            <LoadingSpinner size="sm" />
          ) : digests.length === 0 ? (
            <p className="text-sm text-slate-400">No digests yet</p>
          ) : (
            <div className="space-y-2">
              {digests.map(d => (
                <button
                  key={d.id}
                  onClick={() => { loadDetail(d.id); setActiveJob(null) }}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${
                    selectedDigest?.id === d.id
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="text-sm font-medium text-slate-800">{d.id}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {formatDate(d.date_from)} ~ {formatDate(d.date_to)}
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-xs text-slate-500">{d.task_count} tasks</span>
                    <SeverityBadges counts={d.severity_counts} />
                  </div>
                  {d.edited && (
                    <span className="text-xs text-amber-600 mt-1 inline-block">edited</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Main Content Area */}
        <div className="lg:col-span-3">
          {/* Progress Timeline (when generating) */}
          {showProgress && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">Generation Progress</h2>
                  {isJobRunning && <StatusBadge status="running" />}
                  {isJobDone && <StatusBadge status={activeJob!.status} />}
                </div>
                {isJobRunning && activeJob && (
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <span>{activeJob.date_from} ~ {activeJob.date_to}</span>
                    <ElapsedTime startedAt={activeJob.started_at} />
                  </div>
                )}
              </div>
              <ProgressTimeline
                events={progressEvents}
                isRunning={isJobRunning || false}
              />
            </div>
          )}

          {/* Digest Content Viewer */}
          {loadingDetail ? (
            <div className="flex justify-center py-16">
              <LoadingSpinner size="lg" />
            </div>
          ) : selectedDigest ? (
            <div className="bg-white rounded-lg border border-slate-200">
              {/* Toolbar */}
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
                <div className="flex gap-2">
                  <button
                    onClick={() => setEditMode(false)}
                    className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                      !editMode ? 'bg-slate-100 text-slate-800' : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Preview
                  </button>
                  <button
                    onClick={() => { setEditMode(true); setEditContent(selectedDigest.content) }}
                    className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                      editMode ? 'bg-slate-100 text-slate-800' : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Edit
                  </button>
                </div>
                <div className="flex gap-2">
                  {editMode && (
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="px-3 py-1 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      {saving ? 'Saving...' : 'Save'}
                    </button>
                  )}
                  <button
                    onClick={handleCopyMd}
                    className="px-3 py-1 border border-slate-300 rounded text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                  >
                    Copy MD
                  </button>
                  <button
                    onClick={handleDownloadHtml}
                    className="px-3 py-1 border border-slate-300 rounded text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                  >
                    Download HTML
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="p-6">
                {editMode ? (
                  <textarea
                    value={editContent}
                    onChange={e => setEditContent(e.target.value)}
                    className="w-full h-[600px] font-mono text-sm border border-slate-300 rounded-md p-4 resize-y focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                ) : (
                  <div className="markdown-body">
                    <MarkdownViewer content={selectedDigest.content} />
                  </div>
                )}
              </div>
            </div>
          ) : !showProgress ? (
            <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
              Select a digest from the list or generate a new one
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}


function buildHtmlDownload(id: string, content: string): string {
  return `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weekly Digest - ${id}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 24px; color: #1e293b; line-height: 1.6; }
    h1 { color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; }
    h2 { color: #1e40af; margin-top: 32px; }
    h3 { color: #334155; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    th, td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    blockquote { background: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; margin: 16px 0; }
    a { color: #2563eb; text-decoration: none; }
    a:hover { text-decoration: underline; }
    hr { border: none; border-top: 1px solid #e2e8f0; margin: 24px 0; }
    code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
    ul, ol { padding-left: 24px; }
    li { margin: 4px 0; }
  </style>
</head>
<body>
${markdownToHtml(content)}
</body>
</html>`
}

function markdownToHtml(md: string): string {
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/^---$/gm, '<hr>')
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')

  html = html.replace(
    /^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/gm,
    (_match, header: string, _sep: string, body: string) => {
      const headerCells = header.split('|').filter((c: string) => c.trim())
      const rows = body.trim().split('\n')
      let table = '<table><thead><tr>'
      headerCells.forEach((c: string) => { table += `<th>${c.trim()}</th>` })
      table += '</tr></thead><tbody>'
      rows.forEach((row: string) => {
        const cells = row.split('|').filter((c: string) => c.trim())
        table += '<tr>'
        cells.forEach((c: string) => { table += `<td>${c.trim()}</td>` })
        table += '</tr>'
      })
      table += '</tbody></table>'
      return table
    }
  )

  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
  html = html.replace(/^(?!<[a-z]|$)(.+)$/gm, '<p>$1</p>')

  return html
}
