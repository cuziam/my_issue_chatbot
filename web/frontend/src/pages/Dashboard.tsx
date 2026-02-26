import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useTaskStore } from '../stores/taskStore'
import { useWebSocketContext } from '../contexts/WebSocketContext'
import { api } from '../api/client'
import { STATUS_OPTIONS, REPORT_OPTIONS } from '../constants'
import StatusBadge from '../components/StatusBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'
import { usePagination } from '../hooks/usePagination'
import Pagination from '../components/ui/Pagination'

export default function Dashboard() {
  const { tasks, total, loading, error, filters, setFilter, fetchTasks } = useTaskStore()

  // Auto-refresh when poller completes or a job finishes
  useWebSocketContext(useCallback((msg) => {
    if (msg.type === 'scheduler_poll_completed' || msg.type === 'job_finished') {
      fetchTasks()
    }
  }, [fetchTasks]))
  const [fetchModalOpen, setFetchModalOpen] = useState(false)
  const [fetchTaskId, setFetchTaskId] = useState('')
  const [fetching, setFetching] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [fetchSuccess, setFetchSuccess] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState(filters.search)
  const { page, totalPages, paginated, setPage, totalItems, pageSize } = usePagination(tasks, 20)

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  const handleSearch = useCallback(() => {
    setFilter('search', searchInput)
  }, [searchInput, setFilter])

  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleSearch()
    },
    [handleSearch]
  )

  const handleFetchTask = async () => {
    if (!fetchTaskId.trim()) return
    setFetching(true)
    setFetchError(null)
    setFetchSuccess(null)
    try {
      const result = await api.fetchTask(fetchTaskId.trim())
      setFetchSuccess(result.message || 'Task fetched successfully')
      setFetchTaskId('')
      fetchTasks()
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : 'Failed to fetch task')
    } finally {
      setFetching(false)
    }
  }

  const handleFetchInline = async (taskId: string) => {
    try {
      await api.fetchTask(taskId)
      fetchTasks()
    } catch (e) {
      console.error('Failed to fetch task:', e)
    }
  }

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Task Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {total} tasks total
            {tasks.length !== total && ` (${tasks.length} shown)`}
          </p>
        </div>
        <button
          onClick={() => setFetchModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium shadow-sm transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Fetch Task
        </button>
      </div>

      {/* Fetch Modal */}
      {fetchModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setFetchModalOpen(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Fetch Task from ClickUp</h3>
                <p className="text-xs text-slate-500">Download task data and attachments</p>
              </div>
            </div>
            <input
              type="text"
              value={fetchTaskId}
              onChange={(e) => setFetchTaskId(e.target.value)}
              placeholder="Enter task ID (e.g. IMX-9355)"
              className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-slate-50"
              onKeyDown={(e) => e.key === 'Enter' && handleFetchTask()}
              autoFocus
            />
            {fetchError && (
              <div className="mt-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {fetchError}
              </div>
            )}
            {fetchSuccess && (
              <div className="mt-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                {fetchSuccess}
              </div>
            )}
            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => {
                  setFetchModalOpen(false)
                  setFetchError(null)
                  setFetchSuccess(null)
                }}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Close
              </button>
              <button
                onClick={handleFetchTask}
                disabled={fetching || !fetchTaskId.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm transition-colors"
              >
                {fetching && <LoadingSpinner size="sm" />}
                Fetch
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1.5">Status</label>
            <select
              value={filters.status}
              onChange={(e) => setFilter('status', e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1.5">Report</label>
            <select
              value={filters.hasReport === undefined ? '' : String(filters.hasReport)}
              onChange={(e) => {
                const val = e.target.value
                setFilter('hasReport', val === '' ? undefined : val === 'true')
              }}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {REPORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-medium text-slate-500 mb-1.5">Search</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Search by ID or name..."
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button
                onClick={handleSearch}
                className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-800 text-sm font-medium transition-colors"
              >
                Search
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && <ErrorMessage message={error} onRetry={fetchTasks} />}

      {/* Loading State */}
      {loading && (
        <div className="flex justify-center py-16">
          <LoadingSpinner size="lg" />
        </div>
      )}

      {/* Task Table */}
      {!loading && !error && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="min-w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Assignees
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Report
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Patch
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {paginated.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-16 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <svg className="w-10 h-10 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <p className="text-sm text-slate-500">No tasks found</p>
                      <p className="text-xs text-slate-400">Try adjusting your filters or fetch a new task</p>
                    </div>
                  </td>
                </tr>
              ) : (
                paginated.map((task, idx) => (
                  <tr
                    key={task.id}
                    className={`hover:bg-blue-50/50 transition-colors ${
                      idx !== paginated.length - 1 ? 'border-b border-slate-100' : ''
                    }`}
                  >
                    <td className="px-4 py-3 whitespace-nowrap">
                      <Link to={`/tasks/${task.id}`} className="text-blue-600 hover:text-blue-800 font-semibold text-sm">
                        {task.id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/tasks/${task.id}`} className="text-slate-800 hover:text-blue-600 text-sm transition-colors">
                        {task.name}
                      </Link>
                      {task.tags.length > 0 && (
                        <div className="flex gap-1.5 mt-1.5">
                          {task.tags.map((tag) => (
                            <span
                              key={tag}
                              className="inline-flex items-center px-2 py-0.5 rounded-md text-[0.7rem] font-medium bg-slate-100 text-slate-600 border border-slate-200"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {task.assignees.length === 0 ? (
                          <span className="text-sm text-slate-400">-</span>
                        ) : (
                          task.assignees.slice(0, 2).map((name) => (
                            <span
                              key={name}
                              className="inline-flex items-center gap-1.5 text-xs text-slate-600"
                            >
                              <span className="w-5 h-5 rounded-full bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center text-[0.6rem] font-bold text-slate-600">
                                {name.charAt(0).toUpperCase()}
                              </span>
                              {name}
                            </span>
                          ))
                        )}
                        {task.assignees.length > 2 && (
                          <span className="text-xs text-slate-400">+{task.assignees.length - 2}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {task.has_report ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                          <span className="w-2 h-2 rounded-full bg-emerald-500" />
                          Yes
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {task.has_patch_review ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
                          <span className="w-2 h-2 rounded-full bg-emerald-500" />
                          Yes
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => handleFetchInline(task.id)}
                        className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-blue-600 font-medium transition-colors"
                        title="Refresh task data from ClickUp"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Refresh
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <Pagination page={page} totalPages={totalPages} totalItems={totalItems} pageSize={pageSize} onPageChange={setPage} />
        </div>
      )}
    </div>
  )
}
