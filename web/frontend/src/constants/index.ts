import type { AnalysisMode } from '../types'

export const ANALYSIS_MODES: { value: AnalysisMode; label: string; desc: string }[] = [
  { value: 'initial', label: 'Initial Analysis', desc: 'Researcher + Analyzer team으로 이슈 최초 분석 → report.md 생성' },
  { value: 'verify', label: 'Verify / Review', desc: '개발자 수정 후 검증. 패치 있으면 패치 리뷰, 없으면 대기 또는 verification' },
  { value: 'activity_update', label: 'Activity Update', desc: '새 댓글/본문 변경 감지 후 팔로업. report.md에 추가 분석 append' },
  { value: 'reopen', label: 'Reopen Analysis', desc: '이슈 재발 시 기존 분석 기반 재발 원인 분석' },
]

export const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'qa assigned', label: 'QA Assigned' },
  { value: 'qa to do', label: 'QA To Do' },
  { value: 'qa in review', label: 'QA In Review' },
  { value: 'qa in progress', label: 'QA In Progress' },
  { value: 'completed', label: 'Completed' },
]

export const REPORT_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'true', label: 'Has Report' },
  { value: 'false', label: 'No Report' },
]

export const TOOL_COLORS: Record<string, string> = {
  Read: 'bg-sky-100 text-sky-700',
  Write: 'bg-emerald-100 text-emerald-700',
  Edit: 'bg-amber-100 text-amber-700',
  Glob: 'bg-purple-100 text-purple-700',
  Grep: 'bg-purple-100 text-purple-700',
  Bash: 'bg-slate-200 text-slate-700',
  Task: 'bg-blue-100 text-blue-700',
  SendMessage: 'bg-indigo-100 text-indigo-700',
  TeamCreate: 'bg-pink-100 text-pink-700',
  TeamDelete: 'bg-pink-100 text-pink-700',
  TaskCreate: 'bg-orange-100 text-orange-700',
  TaskUpdate: 'bg-orange-100 text-orange-700',
  TaskList: 'bg-orange-100 text-orange-700',
  TaskGet: 'bg-orange-100 text-orange-700',
}

export const TOOL_COLOR_DEFAULT = 'bg-slate-100 text-slate-600'
