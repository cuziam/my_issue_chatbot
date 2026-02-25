export interface TaskSummary {
  id: string
  name: string
  status: string
  assignees: string[]
  tags: string[]
  has_report: boolean
  has_patch_review: boolean
  has_context: boolean
  url: string
}

export interface TaskDetail extends TaskSummary {
  description: string
  markdown_description: string
  custom_fields: Record<string, string>
  comments: Comment[]
  attachments: Attachment[]
  linked_docs: DocLink[]
  report_content: string | null
  patch_review_content: string | null
  context_content: string | null
  patch_diff_content: string | null
}

export interface Comment {
  date: string
  user: string
  user_id: string
  comment: string
}

export interface Attachment {
  path: string
  original_name: string
  type: string
  extracted_dir?: string
  extracted_files?: { name: string; size: number }[]
}

export interface DocLink {
  doc_id: string
  page_id: string
}

export interface ProgressEvent {
  event: 'tool_use' | 'text' | 'result' | 'heartbeat'
  tool?: string
  detail?: string
  subtype?: string
  duration_ms?: number
  num_turns?: number
  cost_usd?: number
  timestamp?: string
}

export interface AnalysisJob {
  id: string
  task_id: string
  mode: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string | null
  finished_at: string | null
  output_lines: string[]
  progress_events?: ProgressEvent[]
  exit_code: number | null
  exit_reason?: string | null
  error: string | null
  session_id?: string | null
  retry_job_id?: string | null
}

export interface HistoryEntry {
  id: string
  task_id: string
  mode: string
  status: string
  started_at: string
  finished_at: string
  exit_code: number | null
  exit_reason?: string | null
  session_id?: string | null
  retry_job_id?: string | null
  output_line_count: number
}

export interface Trigger {
  task_id: string
  custom_id: string
  mode: string
  reason: string
}

export interface StateData {
  last_run: string | null
  tasks: Record<string, StateTask>
}

export interface StateTask {
  status: string
  assignee_ids: string[]
  has_report: boolean
  has_patch_review: boolean
  last_analysis_type: string | null
  last_analysis_time: string | null
  trigger_attempts: Record<string, number>
  date_updated: string | null
  last_comment_date: string | null
  comment_count: number
}

export interface ChatFile {
  name: string
  path: string
  size: number
  modified_at: string
}

export interface ChatAttachment {
  name: string
  path: string
  type: 'image' | 'text' | 'archive'
  size: number
  url?: string
}

export interface CreatedFile {
  name: string
  path: string
  size?: number
  downloadable: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  session_id?: string
  attachments?: ChatAttachment[]
  created_files?: CreatedFile[]
  progress_events?: { event: string; tool?: string; detail?: string }[]
}

export interface ChatSession {
  session_id: string
  job_id: string
  mode: string
  started_at: string
  status: string
  source: 'analysis' | 'chat'
}

export type AnalysisMode = 'initial' | 'verification' | 'activity_update' | 'patch_review' | 'review'
