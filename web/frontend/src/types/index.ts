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
  replies?: Comment[]
}

export interface Attachment {
  path: string
  original_name: string
  type: string
  url?: string
  extracted_dir?: string
  extracted_files?: { name: string; size: number }[]
}

export interface DocLink {
  doc_id: string
  page_id: string
}

export interface ProgressEvent {
  event: 'tool_use' | 'text' | 'result' | 'heartbeat' | 'cleanup'
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
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'pending_resources'
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
  pending_reason?: string
  deferred?: boolean
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

export interface TaskFileEntry {
  name: string
  path: string
  relative_path?: string | null
  size: number
  modified_at?: string
  ext?: string
  is_image?: boolean
  preview_url?: string
}

export interface TaskFileCategory {
  id: string
  label: string
  icon: string
  files: TaskFileEntry[]
  archive_groups: Record<string, TaskFileEntry[]>
}

export interface TaskFilesResponse {
  categories: TaskFileCategory[]
  total_count: number
}

export type AnalysisMode = 'initial' | 'verify' | 'activity_update' | 'reopen' | 'review' | 'verification' | 'patch_review'

export interface DigestSummary {
  id: string
  date_from: string
  date_to: string
  generated_at: string
  task_count: number
  severity_counts: Record<string, number>
  edited: boolean
  edited_at?: string
  job_id?: string
  issue_type?: string
}

export interface DigestDetail extends DigestSummary {
  content: string
}

export interface DigestJob {
  id: string
  type: string
  status: 'running' | 'completed' | 'failed' | 'error' | 'cancelled'
  date_from: string
  date_to: string
  started_at: string
  finished_at: string | null
  digest_id: string | null
  error: string | null
  progress_events?: { event: string; detail?: string }[]
}

export interface PollLogEntry {
  poll_count: number
  timestamp: string
  status: string
  trigger_count?: number
  started_jobs_count?: number
  error?: string
}

export interface StartedJob {
  job_id: string
  task_id: string
  mode: string
  trigger_reason: string
}

export interface PollResult {
  status: string
  api_task_count?: number
  trigger_count: number
  triggers: Trigger[]
  started_jobs: StartedJob[]
  timestamp: string
  message?: string
}

export interface PollerStatus {
  enabled: boolean
  interval_minutes: number
  last_poll: string | null
  last_poll_result: PollResult | null
  poll_count: number
  error_count: number
  last_error: string | null
  auto_analyze: boolean
  next_poll: string | null
  pending_triggers: Trigger[]
  poll_log: PollLogEntry[]
}

export interface UploadJob {
  upload_id: string
  filename: string
  package_name: string
  status: 'uploading' | 'processing' | 'completed' | 'failed' | 'cancelled'
  phase: 'uploading' | 'extracting' | 'refreshing_inventory' | 'decompiling' | 'done' | 'failed'
  percent: number
  uploaded: number
  total_size: number
  started_at: string
  finished_at: string | null
  error: string | null
  cancelled: boolean
  detail?: string
  package_name_result?: string
  components?: string[]
}
