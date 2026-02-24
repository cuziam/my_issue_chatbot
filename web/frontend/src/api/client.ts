import type { TaskSummary, TaskDetail, AnalysisJob, HistoryEntry, Trigger, StateData, AnalysisMode, ChatSession, ChatMessage } from '../types'

const BASE_URL = '/api'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`)
  }
  return response.json()
}

export const api = {
  // Tasks
  listTasks: (params?: { status?: string; search?: string; has_report?: boolean }) => {
    const searchParams = new URLSearchParams()
    if (params?.status) searchParams.set('status', params.status)
    if (params?.search) searchParams.set('search', params.search)
    if (params?.has_report !== undefined) searchParams.set('has_report', String(params.has_report))
    const qs = searchParams.toString()
    return fetchJSON<{ tasks: TaskSummary[]; total: number }>(`/tasks${qs ? '?' + qs : ''}`)
  },
  getTask: (id: string) => fetchJSON<TaskDetail>(`/tasks/${id}`),
  fetchTask: (id: string) => fetchJSON<{ status: string; message: string }>(`/tasks/${id}/fetch`, { method: 'POST' }),

  // Analysis
  startAnalysis: (taskId: string, mode: AnalysisMode) =>
    fetchJSON<AnalysisJob>('/analysis/start', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, mode }),
    }),
  getJobs: () => fetchJSON<{ jobs: AnalysisJob[] }>('/analysis/jobs'),
  getJob: (id: string) => fetchJSON<AnalysisJob>(`/analysis/jobs/${id}`),
  cancelJob: (id: string) => fetchJSON<{ status: string }>(`/analysis/jobs/${id}/cancel`, { method: 'POST' }),
  getHistory: () => fetchJSON<{ history: HistoryEntry[] }>('/analysis/history'),
  getJobLog: (jobId: string) => fetchJSON<{ lines: string[]; exists: boolean }>(`/analysis/jobs/${jobId}/log`),

  // Scheduler
  detectTriggers: () =>
    fetchJSON<{ triggers: Trigger[]; api_task_count: number }>('/scheduler/detect', { method: 'POST' }),
  runScheduler: (dryRun = true) =>
    fetchJSON<{ stdout: string; stderr: string; return_code: number }>(`/scheduler/run?dry_run=${dryRun}`, {
      method: 'POST',
    }),
  initState: () => fetchJSON<{ task_count: number }>('/scheduler/init-state', { method: 'POST' }),

  // Patches
  fetchDoc: (taskId: string, dryRun = false) =>
    fetchJSON<{ status: string; files: string[]; doc_links: string[] }>(
      `/patches/${taskId}/fetch-doc?dry_run=${dryRun}`,
      { method: 'POST' }
    ),
  generateDiff: (taskId: string) =>
    fetchJSON<{ status: string; file_count: number }>(`/patches/${taskId}/generate-diff`, { method: 'POST' }),

  // State
  getState: () => fetchJSON<StateData>('/state'),
  resetAttempts: (taskId: string, mode?: string) => {
    const qs = mode ? `?mode=${mode}` : ''
    return fetchJSON<{ status: string }>(`/state/tasks/${taskId}/reset-attempts${qs}`, { method: 'PUT' })
  },

  // Chat
  chatSessions: (taskId: string) =>
    fetchJSON<{ sessions: ChatSession[] }>(`/chat/${taskId}/sessions`),
  chatHistory: (taskId: string) =>
    fetchJSON<{ messages: ChatMessage[] }>(`/chat/${taskId}/history`),
  chatSend: (taskId: string, sessionId: string | null, message: string) =>
    fetchJSON<{ chat_id: string; session_id: string; status: string; is_new_session: boolean }>(`/chat/${taskId}/send`, {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, message }),
    }),
  chatCancel: (chatId: string) =>
    fetchJSON<{ status: string }>(`/chat/active/${chatId}/cancel`, { method: 'POST' }),

  // Settings
  getConfig: () => fetchJSON<Record<string, unknown>>('/settings/config'),
  updateConfig: (data: Record<string, unknown>) =>
    fetchJSON<{ status: string }>('/settings/config', { method: 'PUT', body: JSON.stringify({ data }) }),
  getEnv: () => fetchJSON<{ variables: Record<string, string> }>('/settings/env'),
  updateEnv: (variables: Record<string, string>) =>
    fetchJSON<{ status: string }>('/settings/env', { method: 'PUT', body: JSON.stringify({ variables }) }),
  getInventory: () => fetchJSON<{ packages: Record<string, unknown>[]; generated_at: string }>('/settings/inventory'),
  refreshInventory: () =>
    fetchJSON<{ packages: Record<string, unknown>[] }>('/settings/inventory/refresh', { method: 'POST' }),
}
