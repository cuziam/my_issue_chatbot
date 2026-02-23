import { create } from 'zustand'
import type { TaskSummary } from '../types'
import { api } from '../api/client'

interface TaskStore {
  tasks: TaskSummary[]
  total: number
  loading: boolean
  error: string | null
  filters: {
    status: string
    search: string
    hasReport: boolean | undefined
  }
  setFilter: (key: string, value: unknown) => void
  fetchTasks: () => Promise<void>
}

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: [],
  total: 0,
  loading: false,
  error: null,
  filters: { status: '', search: '', hasReport: undefined },
  setFilter: (key, value) => {
    set((s) => ({ filters: { ...s.filters, [key]: value } }))
    get().fetchTasks()
  },
  fetchTasks: async () => {
    set({ loading: true, error: null })
    try {
      const { status, search, hasReport } = get().filters
      const result = await api.listTasks({
        status: status || undefined,
        search: search || undefined,
        has_report: hasReport,
      })
      set({ tasks: result.tasks, total: result.total })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to fetch tasks'
      set({ error: msg })
      console.error('Failed to fetch tasks:', e)
    } finally {
      set({ loading: false })
    }
  },
}))
