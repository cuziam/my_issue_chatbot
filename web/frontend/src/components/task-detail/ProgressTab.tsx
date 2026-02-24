import type { AnalysisJob, ProgressEvent } from '../../types'
import ProgressTimeline from '../ProgressTimeline'
import AnalysisLog from '../AnalysisLog'
import EmptyState from '../ui/EmptyState'
import { useState } from 'react'

type LogView = 'progress' | 'raw'

export default function ProgressTab({
  latestJob,
  isJobRunning,
  jobElapsed,
  jobProgress,
  jobOutput,
}: {
  latestJob: AnalysisJob | null
  isJobRunning: boolean
  jobElapsed: number
  jobProgress: ProgressEvent[]
  jobOutput: string[]
}) {
  const [logView, setLogView] = useState<LogView>('progress')

  if (!latestJob) {
    return <EmptyState text="No analysis job for this task" />
  }

  return (
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
  )
}
