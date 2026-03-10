import { useState } from 'react'
import type { TaskFilesResponse, TaskFileEntry, TaskFileCategory } from '../../types'
import { api } from '../../api/client'

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function getFileTypeIcon(type: string): string {
  switch (type) {
    case 'image': return 'img'
    case 'archive': return 'zip'
    default: return 'txt'
  }
}

// ---------------------------------------------------------------------------
// Category icon helpers
// ---------------------------------------------------------------------------

function getCategoryIcon(icon: string) {
  switch (icon) {
    case 'image':
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      )
    case 'patch':
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
      )
    case 'upload':
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      )
    case 'ai':
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      )
    case 'report':
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      )
    default:
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
      )
  }
}

function getFileIcon(file: TaskFileEntry) {
  if (file.is_image) return '🖼'
  const ext = file.ext || ''
  if (['.zip', '.tar', '.gz', '.7z', '.rar'].includes(ext)) return '📦'
  if (['.md'].includes(ext)) return '📝'
  if (['.json'].includes(ext)) return '📋'
  if (['.log', '.txt'].includes(ext)) return '📄'
  if (['.java', '.py', '.js', '.ts'].includes(ext)) return '💻'
  return '📄'
}

function countCategoryFiles(cat: TaskFileCategory): number {
  let n = cat.files.length
  for (const files of Object.values(cat.archive_groups)) {
    n += files.length
  }
  return n
}

// ---------------------------------------------------------------------------
// FileRow — single file entry
// ---------------------------------------------------------------------------

interface FileRowProps {
  file: TaskFileEntry
  onDownload: () => void
  onReference: () => void
  onImageClick?: () => void
  onDelete?: () => void
}

function FileRow({ file, onDownload, onReference, onImageClick, onDelete }: FileRowProps) {
  return (
    <div
      className="group flex items-center gap-1.5 px-3 py-1.5 hover:bg-slate-100 transition-colors"
      title={`${file.name} (${formatFileSize(file.size)})`}
    >
      {/* Thumbnail or icon */}
      {file.is_image && file.preview_url ? (
        <img
          src={file.preview_url}
          alt={file.name}
          className="w-6 h-6 rounded object-cover flex-shrink-0 cursor-pointer border border-slate-200"
          onClick={onImageClick}
        />
      ) : (
        <span className="w-6 h-6 flex items-center justify-center text-xs flex-shrink-0">
          {getFileIcon(file)}
        </span>
      )}

      {/* File info */}
      <div className="flex-1 min-w-0">
        <div className="text-[11px] font-medium text-slate-700 truncate">{file.name}</div>
        <div className="text-[10px] text-slate-400">{formatFileSize(file.size)}</div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-0 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
        <button
          onClick={(e) => { e.stopPropagation(); onReference() }}
          className="p-1 text-slate-400 hover:text-violet-600 rounded transition-colors"
          title="Insert path to chat"
        >
          <span className="text-[11px] font-bold">@</span>
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDownload() }}
          className="p-1 text-slate-400 hover:text-violet-600 rounded transition-colors"
          title="Download"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
        {onDelete && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="p-1 text-slate-400 hover:text-red-600 rounded transition-colors"
            title="Delete"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ChatFileList — category-based file browser (TaskFilesPanel)
// ---------------------------------------------------------------------------

export interface ChatFileListProps {
  taskFiles: TaskFilesResponse | null
  taskId: string
  onRefresh: () => void
  onFileReference: (filePath: string) => void
  onImagePreview: (url: string) => void
}

export default function ChatFileList({ taskFiles, taskId, onRefresh, onFileReference, onImagePreview }: ChatFileListProps) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(() => new Set())
  const [collapsedArchives, setCollapsedArchives] = useState<Set<string>>(() => new Set())

  const toggleCategory = (id: string) => {
    setCollapsedCategories(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleArchive = (key: string) => {
    setCollapsedArchives(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }

  const handleDelete = async (filename: string) => {
    try {
      await api.chatDeleteFile(taskId, filename)
      onRefresh()
    } catch { /* ignore */ }
  }

  const totalCount = taskFiles?.total_count ?? 0

  return (
    <div className="w-72 border-l border-slate-200 bg-slate-50/50 flex flex-col overflow-hidden flex-shrink-0">
      <div className="px-3 py-2.5 border-b border-slate-200 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-600">Task Files ({totalCount})</span>
        <button
          onClick={onRefresh}
          className="p-1 text-slate-400 hover:text-slate-600 rounded transition-colors"
          title="Refresh"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {!taskFiles || taskFiles.categories.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 px-4">
            <svg className="w-10 h-10 mb-2 text-slate-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <p className="text-xs text-center">No files yet</p>
            <p className="text-[10px] text-slate-300 mt-1 text-center">Task files will appear here</p>
          </div>
        ) : (
          <div className="py-1">
            {taskFiles.categories.map(cat => {
              const isCollapsed = collapsedCategories.has(cat.id)
              const fileCount = countCategoryFiles(cat)
              const isAiFiles = cat.id === 'ai_files'

              return (
                <div key={cat.id}>
                  {/* Category header */}
                  <button
                    onClick={() => toggleCategory(cat.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-100 transition-colors text-left"
                  >
                    <span className={`text-[10px] text-slate-400 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}>
                      ▶
                    </span>
                    <span className="text-slate-500">{getCategoryIcon(cat.icon)}</span>
                    <span className="text-xs font-semibold text-slate-700 flex-1">{cat.label}</span>
                    <span className="text-[10px] text-slate-400">({fileCount})</span>
                  </button>

                  {!isCollapsed && (
                    <div className="ml-3">
                      {/* Direct files */}
                      {cat.files.map(file => (
                        <FileRow
                          key={file.path}
                          file={file}
                          onDownload={() => api.chatDownload(file.path)}
                          onReference={() => onFileReference(file.path)}
                          onImageClick={file.is_image && file.preview_url ? () => onImagePreview(file.preview_url!) : undefined}
                          onDelete={isAiFiles ? () => handleDelete(file.name) : undefined}
                        />
                      ))}

                      {/* Archive groups */}
                      {Object.entries(cat.archive_groups).map(([archiveName, archiveFiles]) => {
                        const archiveKey = `${cat.id}:${archiveName}`
                        const archiveCollapsed = collapsedArchives.has(archiveKey)

                        return (
                          <div key={archiveKey}>
                            <button
                              onClick={() => toggleArchive(archiveKey)}
                              className="w-full flex items-center gap-1.5 px-3 py-1.5 hover:bg-slate-100 transition-colors text-left"
                            >
                              <span className={`text-[10px] text-slate-400 transition-transform ${archiveCollapsed ? '' : 'rotate-90'}`}>
                                ▶
                              </span>
                              <span className="text-[10px]">📦</span>
                              <span className="text-[11px] font-medium text-slate-600 flex-1 truncate">{archiveName}/</span>
                              <span className="text-[10px] text-slate-400">({archiveFiles.length})</span>
                            </button>
                            {!archiveCollapsed && (
                              <div className="ml-4">
                                {archiveFiles.map(file => (
                                  <FileRow
                                    key={file.path}
                                    file={file}
                                    onDownload={() => api.chatDownload(file.path)}
                                    onReference={() => onFileReference(file.path)}
                                    onImageClick={file.is_image && file.preview_url ? () => onImagePreview(file.preview_url!) : undefined}
                                  />
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
