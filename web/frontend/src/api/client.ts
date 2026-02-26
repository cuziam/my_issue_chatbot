import type { TaskSummary, TaskDetail, AnalysisJob, HistoryEntry, Trigger, StateData, AnalysisMode, ChatSession, ChatMessage, ChatAttachment, ChatFile, TaskFilesResponse, UploadJob } from '../types'

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
  chatHistory: (taskId: string, sessionId?: string) => {
    const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
    return fetchJSON<{ messages: ChatMessage[] }>(`/chat/${taskId}/history${qs}`)
  },
  chatUpload: async (taskId: string, file: File): Promise<ChatAttachment & { url: string }> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${BASE_URL}/chat/${taskId}/upload`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(`HTTP ${response.status}: ${text}`)
    }
    return response.json()
  },
  chatSend: (taskId: string, sessionId: string | null, message: string, attachments?: ChatAttachment[]) =>
    fetchJSON<{ chat_id: string; session_id: string; status: string; is_new_session: boolean }>(`/chat/${taskId}/send`, {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, message, attachments: attachments ?? [] }),
    }),
  chatTaskFiles: (taskId: string) =>
    fetchJSON<TaskFilesResponse>(`/chat/${taskId}/task-files`),
  chatFiles: (taskId: string) =>
    fetchJSON<{ files: ChatFile[] }>(`/chat/${taskId}/files`),
  chatDeleteFile: (taskId: string, filename: string) =>
    fetchJSON<{ status: string }>(`/chat/${taskId}/files/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    }),
  chatCancel: (chatId: string) =>
    fetchJSON<{ status: string }>(`/chat/active/${chatId}/cancel`, { method: 'POST' }),
  chatDownload: (path: string) => {
    const url = `${BASE_URL}/chat/download?path=${encodeURIComponent(path)}`
    const a = document.createElement('a')
    a.href = url
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  },

  // Packages
  uploadPackage: (
    file: File,
    onProgress?: (pct: number) => void,
    xhrRef?: { current: XMLHttpRequest | null },
  ): Promise<{ upload_id: string; status: string; filename: string }> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      if (xhrRef) xhrRef.current = xhr

      xhr.open('POST', `${BASE_URL}/packages/upload`)

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText))
          } catch {
            resolve({ upload_id: '', status: 'ok', filename: file.name })
          }
        } else {
          reject(new Error(`HTTP ${xhr.status}: ${xhr.responseText}`))
        }
      }

      xhr.onerror = () => reject(new Error('Network error during upload'))
      xhr.ontimeout = () => reject(new Error('Upload timed out'))
      xhr.onabort = () => reject(new Error('Upload cancelled'))

      const formData = new FormData()
      formData.append('file', file)
      xhr.send(formData)
    })
  },
  getUploadJobs: () => fetchJSON<{ jobs: UploadJob[] }>('/packages/upload/jobs'),
  cancelUpload: (id: string) =>
    fetchJSON<{ status: string }>(`/packages/upload/jobs/${id}/cancel`, { method: 'POST' }),
  deletePackage: (name: string) =>
    fetchJSON<{ status: string }>(`/packages/${encodeURIComponent(name)}`, { method: 'DELETE' }),

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
