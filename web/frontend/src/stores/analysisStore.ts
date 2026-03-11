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
  updateJobMode: (jobId: string, mode: string) => void
  setJobs: (jobs: AnalysisJob[]) => void
  selectJob: (jobId: string | null) => void
  clearCompletedJobs: () => Promise<void>
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
      const sorted = [...result.jobs].sort(
        (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
      )
      set((s) => ({
        jobs: sorted,
        progressEvents: { ...s.progressEvents, ...pe },
      }))
    } catch (e) {
      console.error('Failed to fetch jobs:', e)
    }
  },
  fetchHistory: async () => {
    try {
      const result = await api.getHistory()
      const sorted = result.history.sort(
        (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
      )
      set({ history: sorted })
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
  updateJobMode: (jobId, mode) => {
    set((s) => ({
      jobs: s.jobs.map((j) => (j.id === jobId ? { ...j, mode } : j)),
    }))
  },
  setJobs: (jobs) => set({ jobs }),
  selectJob: (jobId) => set({ selectedJobId: jobId }),
  clearCompletedJobs: async () => {
    try {
      await api.clearCompletedJobs()
      set((s) => {
        const remaining = s.jobs.filter(
          (j) => j.status === 'running' || j.status === 'pending'
        )
        const cleared = s.jobs.filter(
          (j) => j.status !== 'running' && j.status !== 'pending'
        )
        const clearedIds = new Set(cleared.map((j) => j.id))
        return {
          jobs: remaining,
          selectedJobId: s.selectedJobId && clearedIds.has(s.selectedJobId) ? null : s.selectedJobId,
        }
      })
    } catch (e) {
      console.error('Failed to clear completed jobs:', e)
    }
  },
}))
