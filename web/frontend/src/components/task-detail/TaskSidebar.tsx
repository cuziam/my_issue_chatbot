import { useState } from 'react'
import type { TaskDetail as TaskDetailType, AnalysisMode } from '../../types'
import { ANALYSIS_MODES } from '../../constants'
import LoadingSpinner from '../LoadingSpinner'

interface TaskSidebarProps {
  task: TaskDetailType
  analyzeOpen: boolean
  setAnalyzeOpen: (v: boolean) => void
  assigneesExpanded: boolean
  setAssigneesExpanded: (v: boolean) => void
  actionLoading: string | null
  onAnalyze: (mode: AnalysisMode) => void
  onCancelJob: () => void
  onAction: (name: string, fn: () => Promise<unknown>) => void
  onTabChange: (tab: string) => void
  api: {
    fetchTask: (id: string) => Promise<unknown>
    fetchDoc: (id: string) => Promise<unknown>
    generateDiff: (id: string) => Promise<unknown>
  }
}

function formatFieldValue(key: string, value: string): string {
  // Detect date fields by key name and timestamp-like values (13-digit ms)
  const dateKeywords = ['date', 'deadline', '희망일', '승인']
  const isDateKey = dateKeywords.some(kw => key.toLowerCase().includes(kw))
  if (isDateKey && /^\d{13}$/.test(String(value))) {
    const d = new Date(Number(value))
    if (!isNaN(d.getTime())) {
      const yy = String(d.getFullYear()).slice(2)
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      return `${yy}/${mm}/${dd}`
    }
  }
  return String(value)
}

export default function TaskSidebar({
  task,
  analyzeOpen,
  setAnalyzeOpen,
  assigneesExpanded,
  setAssigneesExpanded,
  actionLoading,
  onAnalyze,
  onCancelJob,
  onAction,
  onTabChange,
  api,
}: TaskSidebarProps) {
  const [debugExpanded, setDebugExpanded] = useState(false)
  const visibleAssignees = assigneesExpanded ? task.assignees : task.assignees.slice(0, 3)
  const hasMoreAssignees = task.assignees.length > 3
  const versionFields = Object.entries(task.custom_fields).filter(([k]) => k.toLowerCase().includes('version'))
  const otherFields = Object.entries(task.custom_fields).filter(([k]) => !k.toLowerCase().includes('version'))

  return (
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
                <dd className="text-sm text-slate-800 mt-0.5">{formatFieldValue(key, String(value))}</dd>
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
            { label: 'Report', has: task.has_report, tab: 'report' },
            { label: 'Patch Review', has: task.has_patch_review, tab: 'patch_review' },
            { label: 'Patch Diff', has: !!task.patch_diff_content, tab: 'patch_diff' },
          ].map((item) => (
            <li key={item.label} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${item.has ? 'bg-emerald-500' : 'bg-slate-200'}`} />
                <span className={`text-sm ${item.has ? 'text-slate-700' : 'text-slate-400'}`}>{item.label}</span>
              </div>
              {item.has && (
                <button onClick={() => onTabChange(item.tab)} className="text-xs text-blue-600 hover:text-blue-800">View</button>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* Actions */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Actions</h3>
        <div className="space-y-2">
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
                    onClick={() => onAnalyze(mode.value)}
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
              onClick={() => onAction(action.name, action.fn)}
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

      {/* Debug */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <button
          onClick={() => setDebugExpanded(!debugExpanded)}
          className="flex items-center justify-between w-full text-xs font-semibold text-slate-400 uppercase tracking-wider"
        >
          Debug
          <svg className={`w-3.5 h-3.5 transition-transform ${debugExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {debugExpanded && (
          <div className="mt-3 space-y-2">
            <button
              onClick={() => onTabChange('context')}
              className="w-full text-left px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-2 transition-colors"
            >
              <span className={`w-2 h-2 rounded-full ${task.context_content ? 'bg-emerald-500' : 'bg-slate-200'}`} />
              Context
            </button>
            <button
              onClick={() => onTabChange('raw')}
              className="w-full text-left px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-2 transition-colors"
            >
              <span className="w-2 h-2 rounded-full bg-slate-400" />
              Raw JSON
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
