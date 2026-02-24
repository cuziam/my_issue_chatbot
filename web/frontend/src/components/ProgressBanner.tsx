import { useState } from 'react'
import type { AnalysisJob, ProgressEvent } from '../types'
import LoadingSpinner from './LoadingSpinner'
import ProgressTimeline from './ProgressTimeline'

interface ProgressBannerProps {
  job: AnalysisJob
  elapsed: number
  progress: ProgressEvent[]
  onCancel: () => void
  onViewReport?: () => void
}

export default function ProgressBanner({ job, elapsed, progress, onCancel, onViewReport }: ProgressBannerProps) {
  const [expanded, setExpanded] = useState(false)
  const isRunning = job.status === 'running'
  const isCompleted = job.status === 'completed'
  const isFailed = job.status === 'failed'
  const lastEvent = progress.length > 0 ? progress[progress.length - 1] : null

  if (isCompleted || isFailed) {
    return (
      <div className={`mb-4 rounded-lg border px-4 py-3 ${isCompleted ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-medium ${isCompleted ? 'text-emerald-800' : 'text-red-800'}`}>
              {isCompleted ? 'Analysis complete' : 'Analysis failed'}
            </span>
            <span className="text-xs text-slate-500 bg-white/60 px-2 py-0.5 rounded">{job.mode}</span>
          </div>
          <div className="flex items-center gap-2">
            {isCompleted && onViewReport && (
              <button onClick={onViewReport} className="text-xs font-medium text-emerald-700 hover:text-emerald-900 underline">
                View Report
              </button>
            )}
            <button onClick={() => setExpanded(!expanded)} className="text-xs text-slate-500 hover:text-slate-700">
              {expanded ? 'Hide' : 'Details'}
            </button>
          </div>
        </div>
        {expanded && (
          <div className="mt-3 pt-3 border-t border-slate-200/50">
            <ProgressTimeline events={progress} isRunning={false} />
          </div>
        )}
      </div>
    )
  }

  if (!isRunning) return null

  return (
    <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 overflow-hidden">
      <div className="px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LoadingSpinner size="sm" />
            <span className="text-sm font-medium text-blue-800">
              Analyzing ({job.mode})
            </span>
            <span className="text-xs text-blue-600">
              {Math.floor(elapsed / 60)}m {elapsed % 60}s
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => setExpanded(!expanded)} className="text-xs font-medium text-blue-600 hover:text-blue-800">
              {expanded ? 'Collapse' : 'Full View'}
            </button>
            <button onClick={onCancel} className="text-xs font-medium text-red-600 hover:text-red-800">
              Cancel
            </button>
          </div>
        </div>
        {lastEvent && !expanded && (
          <div className="mt-1.5 text-xs text-blue-600 truncate">
            {lastEvent.event === 'tool_use' && lastEvent.tool
              ? `${lastEvent.tool}: ${lastEvent.detail}`
              : lastEvent.detail}
          </div>
        )}
      </div>
      {expanded && (
        <div className="border-t border-blue-200">
          <ProgressTimeline events={progress} isRunning={true} />
        </div>
      )}
    </div>
  )
}
