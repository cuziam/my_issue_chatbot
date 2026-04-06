import type { Trigger } from '../../types'
import StatusBadge from '../../components/StatusBadge'
import LoadingSpinner from '../../components/LoadingSpinner'
import Pagination from '../../components/ui/Pagination'
import { usePagination } from '../../hooks/usePagination'

export interface TriggerListProps {
  dedupedTriggers: Trigger[]
  manualTriggers: Trigger[] | null
  detectApiCount: number | null
  detectLoading: boolean
  initLoading: boolean
  initResult: string | null
  selectedTriggers: Set<string>
  analyzeLoading: string | null
  triggerKey: (t: Trigger) => string
  onDetect: () => void
  onInitState: () => void
  onSelectTrigger: (t: Trigger) => void
  onSelectAll: () => void
  onAnalyzeTrigger: (t: Trigger) => void
  onDismissTrigger: (t: Trigger) => void
  onAnalyzeSelected: () => void
}

export default function TriggerList({
  dedupedTriggers,
  manualTriggers,
  detectApiCount,
  detectLoading,
  initLoading,
  initResult,
  selectedTriggers,
  analyzeLoading,
  triggerKey,
  onDetect,
  onInitState,
  onSelectTrigger,
  onSelectAll,
  onAnalyzeTrigger,
  onDismissTrigger,
  onAnalyzeSelected,
}: TriggerListProps) {
  const triggersPg = usePagination(dedupedTriggers, 20)

  return (
    <>
      {/* Actions Card (Detect + Init) */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <h2 className="text-sm font-semibold text-slate-800">Manual Actions</h2>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={onDetect}
            disabled={detectLoading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 shadow-sm transition-colors"
          >
            {detectLoading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            )}
            Detect Triggers
          </button>
          <div className="border-l border-slate-200 h-8 mx-1" />
          <button
            onClick={onInitState}
            disabled={initLoading}
            className="inline-flex items-center gap-2 px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {initLoading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
            Init State
          </button>
        </div>

        {initResult && (
          <div className="mt-3 px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
            {initResult}
          </div>
        )}
      </div>

      {/* Detected Triggers */}
      {dedupedTriggers.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 mb-5 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-800">Detected Triggers</h2>
              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-bold bg-amber-100 text-amber-700">
                {dedupedTriggers.length}
              </span>
              {detectApiCount !== null && (
                <span className="text-xs text-slate-400 ml-2">{detectApiCount} tasks from API</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onSelectAll}
                className="text-xs text-slate-500 hover:text-blue-600 font-medium transition-colors"
              >
                {selectedTriggers.size === dedupedTriggers.length ? 'Deselect All' : 'Select All'}
              </button>
              {selectedTriggers.size > 0 && (
                <button
                  onClick={onAnalyzeSelected}
                  disabled={analyzeLoading === 'bulk'}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-xs font-medium disabled:opacity-50 shadow-sm transition-colors"
                >
                  {analyzeLoading === 'bulk' && <LoadingSpinner size="sm" />}
                  Analyze Selected ({selectedTriggers.size})
                </button>
              )}
            </div>
          </div>
          <table className="min-w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-3 py-2.5 text-center w-10">
                  <input
                    type="checkbox"
                    checked={selectedTriggers.size === dedupedTriggers.length && dedupedTriggers.length > 0}
                    onChange={onSelectAll}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                </th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Task</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Custom ID</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Mode</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Reason</th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {triggersPg.paginated.map((t, idx) => {
                const key = triggerKey(t)
                return (
                  <tr
                    key={key}
                    className={`hover:bg-slate-50 transition-colors ${
                      idx !== triggersPg.paginated.length - 1 ? 'border-b border-slate-100' : ''
                    }`}
                  >
                    <td className="px-3 py-2.5 text-center">
                      <input
                        type="checkbox"
                        checked={selectedTriggers.has(key)}
                        onChange={() => onSelectTrigger(t)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-3 py-2.5 text-sm font-semibold text-slate-800">{t.task_id.slice(0, 8)}</td>
                    <td className="px-3 py-2.5 text-sm text-slate-600 font-mono">{t.custom_id || '-'}</td>
                    <td className="px-3 py-2.5">
                      <StatusBadge status={t.mode} />
                      {t.deferred && (
                        <span className="ml-1.5 px-1.5 py-0.5 text-[10px] bg-amber-100 text-amber-700 rounded font-medium">
                          Waiting
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-sm text-slate-600">{t.reason}</td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => onAnalyzeTrigger(t)}
                          disabled={analyzeLoading === key}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg hover:bg-emerald-100 text-xs font-medium disabled:opacity-50 transition-colors"
                          title="Analyze this trigger"
                        >
                          {analyzeLoading === key ? (
                            <LoadingSpinner size="sm" />
                          ) : (
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                            </svg>
                          )}
                        </button>
                        <button
                          onClick={() => onDismissTrigger(t)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-50 text-slate-500 border border-slate-200 rounded-lg hover:bg-red-50 hover:text-red-600 hover:border-red-200 text-xs font-medium transition-colors"
                          title="Dismiss this trigger"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <Pagination page={triggersPg.page} totalPages={triggersPg.totalPages} totalItems={triggersPg.totalItems} pageSize={triggersPg.pageSize} onPageChange={triggersPg.setPage} />
        </div>
      )}

      {/* Empty triggers result from manual detect */}
      {manualTriggers !== null && dedupedTriggers.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 mb-5 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-800">Detected Triggers</h2>
              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-bold bg-slate-100 text-slate-500">0</span>
            </div>
            {detectApiCount !== null && (
              <span className="text-xs text-slate-400">{detectApiCount} tasks from API</span>
            )}
          </div>
          <div className="px-5 py-8 text-center">
            <svg className="w-8 h-8 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-slate-500">No triggers detected</p>
          </div>
        </div>
      )}
    </>
  )
}
