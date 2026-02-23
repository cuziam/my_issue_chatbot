import { create } from 'zustand'
import type { AnalysisJob, HistoryEntry, ProgressEvent } from '../types'
import { api } from '../api/client'

interface AnalysisStore {
  jobs: AnalysisJob[]
  history: HistoryEntry[]
  activeJobOutput: Record<string, string[]>
  progressEvents: Record<string, ProgressEvent[]>
  selectedJobId: string | null
  fetchJobs: () => Promise<void>
  fetchHistory: () => Promise<void>
  addOutputLine: (jobId: string, line: string) => void
  addProgressEvent: (jobId: string, event: ProgressEvent) => void
  updateJob: (job: AnalysisJob) => void
  setJobs: (jobs: AnalysisJob[]) => void
  selectJob: (jobId: string | null) => void
}

export const useAnalysisStore = create<AnalysisStore>((set) => ({
  jobs: [],
  history: [],
  activeJobOutput: {},
  progressEvents: {},
  selectedJobId: null,
  fetchJobs: async () => {
    try {
      const result = await api.getJobs()
      // Populate progressEvents from fetched jobs (for page refresh mid-analysis)
      const pe: Record<string, ProgressEvent[]> = {}
      for (const job of result.jobs) {
        if (job.progress_events && job.progress_events.length > 0) {
          pe[job.id] = job.progress_events
        }
      }
      set((s) => ({
        jobs: result.jobs,
        progressEvents: { ...s.progressEvents, ...pe },
      }))
    } catch (e) {
      console.error('Failed to fetch jobs:', e)
    }
  },
  fetchHistory: async () => {
    try {
      const result = await api.getHistory()
      set({ history: result.history })
    } catch (e) {
      console.error('Failed to fetch history:', e)
    }
  },
  addOutputLine: (jobId, line) => {
    set((s) => ({
      activeJobOutput: {
        ...s.activeJobOutput,
        [jobId]: [...(s.activeJobOutput[jobId] || []), line],
      },
    }))
  },
  addProgressEvent: (jobId, event) => {
    set((s) => ({
      progressEvents: {
        ...s.progressEvents,
        [jobId]: [...(s.progressEvents[jobId] || []), event],
      },
    }))
  },
  updateJob: (job) => {
    set((s) => ({
      jobs: s.jobs.some((j) => j.id === job.id)
        ? s.jobs.map((j) => (j.id === job.id ? job : j))
        : [job, ...s.jobs],
    }))
  },
  setJobs: (jobs) => set({ jobs }),
  selectJob: (jobId) => set({ selectedJobId: jobId }),
}))
