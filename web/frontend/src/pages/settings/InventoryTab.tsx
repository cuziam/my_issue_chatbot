import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from '../../api/client'
import type { UploadJob } from '../../types'
import { useWebSocketContext } from '../../contexts/WebSocketContext'
import LoadingSpinner from '../../components/LoadingSpinner'
import ErrorMessage from '../../components/ErrorMessage'

const PHASE_LABELS: Record<string, string> = {
  uploading: 'Uploading...',
  extracting: 'Extracting...',
  refreshing_inventory: 'Refreshing inventory...',
  decompiling: 'Decompiling...',
  done: 'Done',
  failed: 'Failed',
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${sizes[i]}`
}

export default function InventoryViewer() {
  const [packages, setPackages] = useState<Record<string, unknown>[] | null>(null)
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Upload state
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadJobs, setUploadJobs] = useState<UploadJob[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [deletingPkg, setDeletingPkg] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const xhrRef = useRef<XMLHttpRequest | null>(null)

  const loadInventory = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getInventory()
      setPackages(data.packages)
      setGeneratedAt(data.generated_at)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load inventory')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadUploadJobs = useCallback(async () => {
    try {
      const data = await api.getUploadJobs()
      const serverIds = new Set(data.jobs.map((j: UploadJob) => j.upload_id))
      // Merge: update local jobs with server state, and mark any local
      // "processing" jobs missing from server as failed (server restarted).
      setUploadJobs((prev) => {
        const merged = prev.map((local) => {
          const server = data.jobs.find((s: UploadJob) => s.upload_id === local.upload_id)
          if (server) return server
          // Local job not on server — if still active, mark as failed
          if (local.status === 'uploading' || local.status === 'processing') {
            return { ...local, status: 'failed' as const, phase: 'failed', error: 'Server restarted during processing' }
          }
          return local
        })
        // Add any server jobs not in local state
        for (const sj of data.jobs) {
          if (!prev.some((l) => l.upload_id === sj.upload_id)) {
            merged.push(sj)
          }
        }
        return merged
      })
      const hasActive = data.jobs.some(
        (j: UploadJob) => j.status === 'uploading' || j.status === 'processing'
      )
      if (hasActive && !uploading) {
        setUploading(true)
      } else if (!hasActive && uploading) {
        setUploading(false)
        if (data.jobs.some((j: UploadJob) => j.status === 'completed')) {
          loadInventory()
        }
      }
    } catch {
      // Silently fail — jobs are non-critical
    }
  }, [uploading, loadInventory])

  useEffect(() => {
    loadInventory()
    loadUploadJobs()
  }, [loadInventory, loadUploadJobs])

  // Listen for WebSocket upload events via global singleton
  useWebSocketContext(useCallback((msg) => {
    if (msg.type === 'upload_progress') {
      setUploadJobs((prev) =>
        prev.map((j) =>
          j.upload_id === msg.upload_id
            ? { ...j, percent: msg.percent, phase: msg.phase }
            : j
        )
      )
    } else if (msg.type === 'upload_phase') {
      setUploadJobs((prev) =>
        prev.map((j) =>
          j.upload_id === msg.upload_id
            ? { ...j, phase: msg.phase, detail: msg.detail, status: 'processing' }
            : j
        )
      )
    } else if (msg.type === 'upload_completed') {
      setUploadJobs((prev) =>
        prev.map((j) =>
          j.upload_id === msg.upload_id
            ? { ...j, status: 'completed', phase: 'done', package_name: msg.package_name, components: msg.components }
            : j
        )
      )
      setUploading(false)
      loadInventory()
    } else if (msg.type === 'upload_failed') {
      setUploadJobs((prev) =>
        prev.map((j) =>
          j.upload_id === msg.upload_id
            ? { ...j, status: 'failed', phase: 'failed', error: msg.error }
            : j
        )
      )
      setUploading(false)
    }
  }, [loadInventory]))

  // Polling fallback: poll upload jobs while uploading
  useEffect(() => {
    if (!uploading) return
    const interval = setInterval(() => {
      loadUploadJobs()
    }, 3000)
    return () => clearInterval(interval)
  }, [uploading, loadUploadJobs])

  // Warn before leaving during upload
  useEffect(() => {
    if (!uploading) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [uploading])

  const handleRefresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      const data = await api.refreshInventory()
      setPackages(data.packages)
      setGeneratedAt(new Date().toISOString())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to refresh inventory')
    } finally {
      setRefreshing(false)
    }
  }

  const startUpload = async (file: File) => {
    setUploadError(null)
    setUploading(true)
    setUploadProgress(0)

    try {
      const result = await api.uploadPackage(
        file,
        (pct) => setUploadProgress(pct),
        xhrRef,
      )
      // Add job to local state
      setUploadJobs((prev) => [
        {
          upload_id: result.upload_id,
          filename: file.name,
          package_name: file.name.replace(/\.(tar\.gz|tar|zip)$/i, ''),
          status: 'processing',
          phase: 'extracting',
          percent: 100,
          uploaded: file.size,
          total_size: file.size,
          started_at: new Date().toISOString(),
          finished_at: null,
          error: null,
          cancelled: false,
        },
        ...prev,
      ])
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      if (msg !== 'Upload cancelled') {
        setUploadError(msg)
      }
      setUploading(false)
    }
  }

  const handleFileSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return
    const file = files[0]
    const name = file.name.toLowerCase()
    if (!name.endsWith('.tar.gz') && !name.endsWith('.tar') && !name.endsWith('.zip')) {
      setUploadError('Unsupported file type. Allowed: .tar.gz, .tar, .zip')
      return
    }
    startUpload(file)
  }

  const handleCancel = async (uploadId: string) => {
    // Abort XHR if still uploading
    if (xhrRef.current) {
      xhrRef.current.abort()
      xhrRef.current = null
    }
    try {
      await api.cancelUpload(uploadId)
    } catch {
      // ignore
    }
    setUploadJobs((prev) =>
      prev.map((j) =>
        j.upload_id === uploadId ? { ...j, status: 'cancelled', phase: 'failed', error: 'Cancelled' } : j
      )
    )
    setUploading(false)
  }

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete package "${name}"? This cannot be undone.`)) return
    setDeletingPkg(name)
    try {
      await api.deletePackage(name)
      await loadInventory()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete package')
    } finally {
      setDeletingPkg(null)
    }
  }

  const handleDismissJob = (uploadId: string) => {
    setUploadJobs((prev) => prev.filter((j) => j.upload_id !== uploadId))
  }

  // Drag & drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(true)
  }
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
    handleFileSelect(e.dataTransfer.files)
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  if (error && !packages) {
    return <ErrorMessage message={error} onRetry={loadInventory} />
  }

  const activeJobs = uploadJobs.filter(
    (j) => j.status === 'uploading' || j.status === 'processing'
  )
  const recentJobs = uploadJobs.filter(
    (j) => j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled'
  ).slice(0, 3)

  return (
    <div
      className={`bg-white rounded-xl border-2 overflow-hidden transition-colors ${
        dragOver ? 'border-blue-400 bg-blue-50/30' : 'border-slate-200'
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Package Inventory</h2>
            {generatedAt && (
              <p className="text-xs text-slate-400">
                Generated {new Date(generatedAt).toLocaleString()}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50 shadow-sm transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            Upload
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".tar.gz,.tar,.zip"
            className="hidden"
            onChange={(e) => handleFileSelect(e.target.files)}
          />
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 shadow-sm transition-colors"
          >
            {refreshing ? (
              <LoadingSpinner size="sm" />
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
            Refresh
          </button>
        </div>
      </div>

      {/* Upload error */}
      {uploadError && (
        <div className="mx-5 mt-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
          <span className="text-sm text-red-700">{uploadError}</span>
          <button
            onClick={() => setUploadError(null)}
            className="text-red-400 hover:text-red-600 ml-3"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Error banner (non-fatal) */}
      {error && packages && (
        <div className="mx-5 mt-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
          {error}
        </div>
      )}

      {/* Active upload jobs */}
      {activeJobs.map((job) => (
        <div
          key={job.upload_id}
          className="mx-5 mt-4 px-4 py-4 bg-blue-50 border border-blue-200 rounded-lg"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-blue-600 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <span className="text-sm font-medium text-blue-900">{job.filename}</span>
              {job.total_size > 0 && (
                <span className="text-xs text-blue-600">({formatBytes(job.total_size)})</span>
              )}
            </div>
            <button
              onClick={() => handleCancel(job.upload_id)}
              className="px-3 py-1 text-xs font-medium text-red-600 hover:text-red-800 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
          {/* Progress bar */}
          <div className="w-full bg-blue-100 rounded-full h-2 mb-1.5">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{
                width: `${job.phase === 'uploading' ? job.percent : 100}%`,
              }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-blue-700">
              {PHASE_LABELS[job.phase] || job.phase}
              {job.detail ? ` ${job.detail}` : ''}
            </span>
            {job.phase === 'uploading' && (
              <span className="text-xs text-blue-600 font-mono">{job.percent}%</span>
            )}
          </div>
        </div>
      ))}

      {/* Recent completed/failed jobs */}
      {recentJobs.map((job) => (
        <div
          key={job.upload_id}
          className={`mx-5 mt-4 px-4 py-3 rounded-lg flex items-center justify-between ${
            job.status === 'completed'
              ? 'bg-emerald-50 border border-emerald-200'
              : 'bg-red-50 border border-red-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {job.status === 'completed' ? (
              <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            )}
            <span className={`text-sm font-medium ${
              job.status === 'completed' ? 'text-emerald-800' : 'text-red-800'
            }`}>
              {job.filename}
              {job.status === 'completed' && ' — uploaded successfully'}
              {job.status === 'failed' && ` — ${job.error || 'failed'}`}
              {job.status === 'cancelled' && ' — cancelled'}
            </span>
          </div>
          <button
            onClick={() => handleDismissJob(job.upload_id)}
            className="text-slate-400 hover:text-slate-600 ml-3"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}

      {/* Drag overlay */}
      {dragOver && (
        <div className="mx-5 mt-4 px-4 py-8 border-2 border-dashed border-blue-400 bg-blue-50/50 rounded-lg text-center">
          <svg className="w-8 h-8 text-blue-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm font-medium text-blue-600">Drop archive here to upload</p>
          <p className="text-xs text-blue-400 mt-1">.tar.gz, .tar, .zip</p>
        </div>
      )}

      {/* Package table */}
      {!packages || packages.length === 0 ? (
        <div className="px-5 py-12 text-center">
          <svg className="w-10 h-10 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <p className="text-sm text-slate-500">No packages found</p>
          <p className="text-xs text-slate-400 mt-1">Upload a .tar.gz or .zip archive to get started</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Package</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Version</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Components</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Path</th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase w-20">Actions</th>
              </tr>
            </thead>
            <tbody>
              {packages.map((pkg, idx) => {
                const name = (pkg.name as string) || (pkg.package_name as string) || `Package ${idx + 1}`
                const version = (pkg.version as string) || '-'
                const components = Array.isArray(pkg.components)
                  ? (pkg.components as string[]).join(', ')
                  : typeof pkg.components === 'object' && pkg.components
                    ? Object.keys(pkg.components).join(', ')
                    : '-'
                const path = (pkg.path as string) || (pkg.dir as string) || '-'
                const extracted = pkg.extracted !== false
                return (
                  <tr
                    key={idx}
                    className={`hover:bg-slate-50 transition-colors ${
                      idx !== packages.length - 1 ? 'border-b border-slate-100' : ''
                    }`}
                  >
                    <td className="px-4 py-2.5 text-sm font-semibold text-slate-800">
                      <div className="flex items-center gap-2">
                        {name}
                        {!extracted && (
                          <span className="text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
                            archive
                          </span>
                        )}
                        {pkg.needs_decompile && (
                          <span className="text-[10px] font-medium text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded">
                            needs decompile
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs font-mono text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
                        {version}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-slate-600">{components || '-'}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-500 font-mono truncate max-w-xs" title={path}>
                      {path}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => handleDelete(name)}
                        disabled={deletingPkg === name}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                        title={`Delete ${name}`}
                      >
                        {deletingPkg === name ? (
                          <LoadingSpinner size="sm" />
                        ) : (
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        )}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
