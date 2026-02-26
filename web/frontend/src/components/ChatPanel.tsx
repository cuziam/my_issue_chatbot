import { useState, useEffect, useRef, useCallback } from 'react'
import type { ChatSession, ChatMessage, ChatAttachment, CreatedFile, TaskFilesResponse, TaskFileEntry, TaskFileCategory } from '../types'
import type { WSMessage } from '../hooks/useWebSocket'
import { useWebSocket } from '../hooks/useWebSocket'
import { useImageLightbox } from '../contexts/ImageLightboxContext'
import { api } from '../api/client'
import MarkdownViewer from './MarkdownViewer'
import LoadingSpinner from './LoadingSpinner'

interface ChatPanelProps {
  taskId: string
  sessions: ChatSession[]
  onSessionCreated?: () => void
  open: boolean
  onClose: () => void
}

interface ChatProgressEvent {
  event: string
  tool?: string
  detail?: string
}

interface PendingFile {
  file: File
  attachment: ChatAttachment
  previewUrl?: string // object URL for image preview
}

const NEW_SESSION = '__new__'
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getFileTypeIcon(type: string): string {
  switch (type) {
    case 'image': return 'img'
    case 'archive': return 'zip'
    default: return 'txt'
  }
}

export default function ChatPanel({ taskId, sessions, onSessionCreated, open, onClose }: ChatPanelProps) {
  const [selectedSession, setSelectedSession] = useState<string | null>(
    sessions.length > 0 ? sessions[0].session_id : null
  )
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [streamingContent, setStreamingContent] = useState('')
  const [activeProgressEvents, setActiveProgressEvents] = useState<ChatProgressEvent[]>([])
  const [activeCreatedFiles, setActiveCreatedFiles] = useState<CreatedFile[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const [uploadingCount, setUploadingCount] = useState(0)
  const [isDragOver, setIsDragOver] = useState(false)
  const [taskFiles, setTaskFiles] = useState<TaskFilesResponse | null>(null)
  const [filesOpen, setFilesOpen] = useState(false)
  const openLightbox = useImageLightbox()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const processedChatIds = useRef<Set<string>>(new Set())
  // Track the session_id for the current active exchange (for tagging messages)
  const activeExchangeSessionRef = useRef<string | null>(null)
  // Track the chat_id via ref (accessible in WS callback without stale closures)
  const activeChatIdRef = useRef<string | null>(null)
  // Skip history load when we just created a new session (prevents wiping optimistic messages)
  const skipNextHistoryLoadRef = useRef(false)
  // Throttle streaming updates: accumulate in ref, flush to state periodically
  const streamingBufferRef = useRef('')
  const streamingFlushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const effectiveSessionId = selectedSession === NEW_SESSION ? null : selectedSession

  // Sync activeExchangeSessionRef when session changes (prevents stale session leaks)
  useEffect(() => {
    activeExchangeSessionRef.current = effectiveSessionId
    // Clear active chat when user manually switches sessions
    // (skipNextHistoryLoadRef is true when handleSend triggers session change — don't clear)
    if (!skipNextHistoryLoadRef.current) {
      activeChatIdRef.current = null
    }
  }, [effectiveSessionId])

  // Load history when task or session changes — backend filters by session_id
  useEffect(() => {
    // Don't load for "New Chat Session" — starts empty
    if (!effectiveSessionId) {
      setMessages([])
      setHistoryLoading(false)
      return
    }
    // Skip history load when we just created this session via handleSend
    // (optimistic user message is already in state, streaming will come via WS)
    if (skipNextHistoryLoadRef.current) {
      skipNextHistoryLoadRef.current = false
      return
    }
    const loadHistory = async () => {
      setHistoryLoading(true)
      try {
        const { messages: hist } = await api.chatHistory(taskId, effectiveSessionId)
        setMessages(hist.map(m => ({
          ...m,
          role: m.role as 'user' | 'assistant',
        })))
      } catch {
        setMessages([])
      } finally {
        setHistoryLoading(false)
      }
    }
    loadHistory()
  }, [taskId, effectiveSessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }, [inputText])

  // Focus textarea when modal opens + ESC to close
  useEffect(() => {
    if (!open) return
    setTimeout(() => textareaRef.current?.focus(), 100)
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [open, onClose])

  // Load all task files on mount
  const loadTaskFiles = useCallback(async () => {
    try {
      setTaskFiles(await api.chatTaskFiles(taskId))
    } catch { /* ignore */ }
  }, [taskId])

  useEffect(() => { loadTaskFiles() }, [loadTaskFiles])

  // Click-to-insert: insert file path into textarea
  const handleFileReference = useCallback((filePath: string) => {
    setInputText(prev => {
      const prefix = prev && !prev.endsWith(' ') ? ' ' : ''
      return prev + prefix + '`' + filePath + '`'
    })
    textareaRef.current?.focus()
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pendingFiles.forEach(pf => {
        if (pf.previewUrl) URL.revokeObjectURL(pf.previewUrl)
      })
      if (streamingFlushTimer.current) clearTimeout(streamingFlushTimer.current)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleWsMessage = useCallback(
    (msg: WSMessage) => {
      // Session guard: check if this WS message belongs to the current active exchange.
      // - If msg has session_id (new backend): match against activeExchangeSessionRef
      // - If msg has no session_id (old backend): match chat_id against activeChatIdRef
      const isChatMsg = msg.type === 'chat_response' || msg.type === 'chat_progress' || msg.type === 'chat_file_created'
      if (isChatMsg && 'chat_id' in msg && msg.task_id === taskId) {
        const sessionOk = msg.session_id
          ? msg.session_id === activeExchangeSessionRef.current
          : msg.chat_id === activeChatIdRef.current
        if (!sessionOk) return
      }

      if (msg.type === 'chat_response' && msg.task_id === taskId) {
        if (msg.done) {
          // Deduplicate: skip if this chat_id was already processed
          if (processedChatIds.current.has(msg.chat_id)) return
          processedChatIds.current.add(msg.chat_id)

          // Clear throttle timer and buffer
          if (streamingFlushTimer.current) {
            clearTimeout(streamingFlushTimer.current)
            streamingFlushTimer.current = null
          }
          streamingBufferRef.current = ''

          setMessages(prev => [
            ...prev,
            {
              role: 'assistant',
              content: msg.content,
              timestamp: new Date().toISOString(),
              session_id: activeExchangeSessionRef.current ?? undefined,
              progress_events: [...activeProgressEvents],
              created_files: msg.created_files ?? (activeCreatedFiles.length > 0 ? [...activeCreatedFiles] : undefined),
            },
          ])
          setStreamingContent('')
          setActiveProgressEvents([])
          setActiveCreatedFiles([])
          setIsLoading(false)
          setActiveChatId(null)
          activeChatIdRef.current = null
        } else {
          // Throttle: buffer in ref, flush to state every 100ms
          streamingBufferRef.current = msg.content
          if (!streamingFlushTimer.current) {
            streamingFlushTimer.current = setTimeout(() => {
              streamingFlushTimer.current = null
              setStreamingContent(streamingBufferRef.current)
            }, 100)
          }
        }
      } else if (msg.type === 'chat_progress' && msg.task_id === taskId) {
        setActiveProgressEvents(prev => [
          ...prev,
          { event: msg.event, tool: msg.tool, detail: msg.detail },
        ])
      } else if (msg.type === 'chat_file_created' && msg.task_id === taskId) {
        setActiveCreatedFiles(prev => [
          ...prev,
          { name: msg.name, path: msg.path, size: msg.size, downloadable: msg.downloadable },
        ])
      } else if (msg.type === 'chat_files_updated' && msg.task_id === taskId) {
        loadTaskFiles()
      }
    },
    [taskId, activeProgressEvents, activeCreatedFiles, loadTaskFiles]
  )

  useWebSocket(handleWsMessage)

  // --- File handling ---
  const handleFiles = useCallback(async (files: FileList | File[]) => {
    const fileArray = Array.from(files)
    for (const file of fileArray) {
      if (file.size > MAX_FILE_SIZE) {
        alert(`File too large: ${file.name} (${formatFileSize(file.size)}). Max ${formatFileSize(MAX_FILE_SIZE)}.`)
        continue
      }

      setUploadingCount(c => c + 1)
      try {
        const result = await api.chatUpload(taskId, file)
        const previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined
        setPendingFiles(prev => [...prev, {
          file,
          attachment: {
            name: result.name,
            path: result.path,
            type: result.type as 'image' | 'text' | 'archive',
            size: result.size,
            url: result.url,
          },
          previewUrl,
        }])
      } catch (e) {
        alert(`Upload failed: ${file.name} - ${e instanceof Error ? e.message : 'Unknown error'}`)
      } finally {
        setUploadingCount(c => c - 1)
      }
    }
  }, [taskId])

  const removePendingFile = useCallback((index: number) => {
    setPendingFiles(prev => {
      const removed = prev[index]
      if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl)
      return prev.filter((_, i) => i !== index)
    })
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files)
    }
  }, [handleFiles])

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData.items
    const imageFiles: File[] = []
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile()
        if (file) {
          // Generate a name for pasted images
          const ext = file.type.split('/')[1] || 'png'
          const named = new File([file], `pasted_image.${ext}`, { type: file.type })
          imageFiles.push(named)
        }
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault()
      handleFiles(imageFiles)
    }
  }, [handleFiles])

  const handleSend = async () => {
    const hasText = inputText.trim().length > 0
    const hasFiles = pendingFiles.length > 0
    if ((!hasText && !hasFiles) || isLoading) return

    const userMessage = inputText.trim()
    const attachments = pendingFiles.map(pf => pf.attachment)

    setInputText('')
    setIsLoading(true)
    setStreamingContent('')
    setActiveProgressEvents([])
    setActiveCreatedFiles([])

    // Clean up preview URLs
    pendingFiles.forEach(pf => {
      if (pf.previewUrl) URL.revokeObjectURL(pf.previewUrl)
    })
    setPendingFiles([])

    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString(),
        session_id: effectiveSessionId ?? undefined,
        attachments: attachments.length > 0 ? attachments : undefined,
      },
    ])

    try {
      const result = await api.chatSend(
        taskId, effectiveSessionId, userMessage,
        attachments.length > 0 ? attachments : undefined
      )
      setActiveChatId(result.chat_id)
      activeChatIdRef.current = result.chat_id
      activeExchangeSessionRef.current = result.session_id
      if (result.is_new_session) {
        // Retroactively tag the optimistic user message with the new session_id
        setMessages(prev => prev.map(m =>
          !m.session_id ? { ...m, session_id: result.session_id } : m
        ))
        // Skip history load — optimistic msg already in state, streaming via WS
        skipNextHistoryLoadRef.current = true
        setSelectedSession(result.session_id)
        onSessionCreated?.()
      }
    } catch (e) {
      setIsLoading(false)
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${e instanceof Error ? e.message : 'Failed to send message'}`,
          timestamp: new Date().toISOString(),
          session_id: activeExchangeSessionRef.current ?? effectiveSessionId ?? undefined,
        },
      ])
    }
  }

  const handleCancel = async () => {
    if (!activeChatId) return
    try {
      await api.chatCancel(activeChatId)
    } catch {
      // ignore
    }
    setIsLoading(false)
    setActiveChatId(null)
    activeChatIdRef.current = null
    if (streamingContent) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: streamingContent + '\n\n*(cancelled)*',
          timestamp: new Date().toISOString(),
          session_id: activeExchangeSessionRef.current ?? undefined,
          created_files: activeCreatedFiles.length > 0 ? [...activeCreatedFiles] : undefined,
        },
      ])
      setStreamingContent('')
    }
    setActiveCreatedFiles([])
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isNewChat = selectedSession === NEW_SESSION || selectedSession === null
  const currentSessionStatus = !isNewChat
    ? sessions.find(s => s.session_id === selectedSession)?.status ?? null
    : null
  const isInterruptedSession = currentSessionStatus === 'interrupted'
  const placeholder = isNewChat
    ? 'Ask about this task... (Shift+Enter for new line)'
    : 'Ask a follow-up question... (Shift+Enter for new line)'
  const canSend = (inputText.trim().length > 0 || pendingFiles.length > 0) && !isLoading && uploadingCount === 0

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-[90vw] max-w-[920px] h-[85vh] max-h-[760px] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Ask AI</h3>
              <p className="text-xs text-slate-400">{taskId}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Files toggle */}
            <button
              onClick={() => setFilesOpen(prev => !prev)}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                filesOpen
                  ? 'bg-violet-50 border-violet-300 text-violet-700'
                  : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
              title="Toggle files panel"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              Files
              {(taskFiles?.total_count ?? 0) > 0 && (
                <span className="ml-0.5 px-1.5 py-0.5 text-[10px] font-bold leading-none rounded-full bg-violet-600 text-white">
                  {taskFiles!.total_count}
                </span>
              )}
            </button>
            {/* Session selector */}
            <select
              value={selectedSession === null ? NEW_SESSION : selectedSession}
              onChange={(e) => setSelectedSession(e.target.value === NEW_SESSION ? NEW_SESSION : e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs bg-slate-50 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent min-w-[180px]"
            >
              <option value={NEW_SESSION}>+ New Chat Session</option>
              {sessions.map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.source === 'chat' ? 'chat' : s.mode} - {s.job_id.substring(0, 8)} ({s.status})
                </option>
              ))}
            </select>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded-lg hover:bg-slate-100"
              title="Close (Esc)"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Messages + Files panel wrapper */}
        <div className="flex-1 flex overflow-hidden">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
            {historyLoading ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner size="md" />
              </div>
            ) : messages.length === 0 && !streamingContent ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400">
                {isInterruptedSession ? (
                  <>
                    <svg className="w-14 h-14 mb-4 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p className="text-base font-medium text-amber-600">Session interrupted</p>
                    <p className="text-sm text-slate-400 mt-1">
                      This session was interrupted before messages could be saved.
                    </p>
                    <p className="text-sm text-slate-400 mt-0.5">
                      You can still send a new message to resume this session.
                    </p>
                  </>
                ) : (
                  <>
                    <svg className="w-14 h-14 mb-4 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    <p className="text-base font-medium text-slate-500">Ask anything about this task</p>
                    <p className="text-sm text-slate-400 mt-1">
                      {isNewChat ? 'A new session will be created' : 'Full context from the selected session'}
                    </p>
                  </>
                )}
              </div>
            ) : (
              <>
                {messages.map((msg, idx) => (
                  <MessageBubble key={idx} message={msg} />
                ))}
                {streamingContent && (
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-white text-xs font-bold">AI</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="bg-slate-50 rounded-xl px-4 py-3 border border-slate-200 text-sm leading-relaxed whitespace-pre-wrap break-words">
                        {streamingContent}
                      </div>
                      {activeCreatedFiles.length > 0 && (
                        <CreatedFilesBar files={activeCreatedFiles} />
                      )}
                      {activeProgressEvents.length > 0 && (
                        <ProgressEvents events={activeProgressEvents} />
                      )}
                    </div>
                  </div>
                )}
                {isLoading && !streamingContent && (
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                      <span className="text-white text-xs font-bold">AI</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <LoadingSpinner size="sm" />
                      Thinking...
                    </div>
                  </div>
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Files panel */}
          {filesOpen && (
            <TaskFilesPanel
              taskFiles={taskFiles}
              taskId={taskId}
              onRefresh={loadTaskFiles}
              onFileReference={handleFileReference}
              onImagePreview={openLightbox}
            />
          )}
        </div>

        {/* File preview area */}
        {(pendingFiles.length > 0 || uploadingCount > 0) && (
          <div className="px-5 py-2 border-t border-slate-100 bg-slate-50/80">
            <div className="flex flex-wrap gap-2">
              {pendingFiles.map((pf, idx) => (
                <FilePreview key={idx} pendingFile={pf} onRemove={() => removePendingFile(idx)} />
              ))}
              {uploadingCount > 0 && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-500">
                  <LoadingSpinner size="sm" />
                  Uploading...
                </div>
              )}
            </div>
          </div>
        )}

        {/* Input area */}
        <div
          className={`px-5 py-4 border-t border-slate-200 bg-slate-50/50 transition-colors ${isDragOver ? 'bg-violet-50 border-violet-300' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {isDragOver && (
            <div className="text-center text-sm text-violet-600 font-medium py-2 mb-2">
              Drop files here to attach
            </div>
          )}
          <div className="flex gap-2 items-end">
            {/* Attach button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              className="p-2.5 text-slate-400 hover:text-violet-600 hover:bg-violet-50 rounded-xl transition-colors disabled:opacity-50 flex-shrink-0"
              title="Attach file"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFiles(e.target.files)
                  e.target.value = '' // reset so same file can be re-selected
                }
              }}
            />
            <textarea
              ref={textareaRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={placeholder}
              disabled={isLoading}
              rows={1}
              className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent disabled:opacity-50 resize-none leading-relaxed"
              style={{ minHeight: '42px', maxHeight: '160px' }}
            />
            {isLoading ? (
              <button
                onClick={handleCancel}
                className="px-4 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 text-sm font-medium transition-colors flex-shrink-0"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!canSend}
                className="px-4 py-2.5 bg-violet-600 text-white rounded-xl hover:bg-violet-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
              >
                Send
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function FilePreview({ pendingFile, onRemove }: { pendingFile: PendingFile; onRemove: () => void }) {
  const { attachment, previewUrl } = pendingFile

  return (
    <div className="relative group flex items-center gap-2 px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs">
      {previewUrl ? (
        <img src={previewUrl} alt={attachment.name} className="w-8 h-8 rounded object-cover" />
      ) : (
        <span className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-[10px] font-bold text-slate-400 uppercase">
          {getFileTypeIcon(attachment.type)}
        </span>
      )}
      <div className="max-w-[120px]">
        <div className="truncate text-slate-700 font-medium">{attachment.name}</div>
        <div className="text-slate-400">{formatFileSize(attachment.size)}</div>
      </div>
      <button
        onClick={onRemove}
        className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-[10px] leading-none"
      >
        x
      </button>
    </div>
  )
}

function AttachmentChip({ attachment }: { attachment: ChatAttachment }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/20 rounded text-[11px]">
      <span className="opacity-70">{getFileTypeIcon(attachment.type)}</span>
      <span className="truncate max-w-[100px]">{attachment.name}</span>
    </span>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const [progressOpen, setProgressOpen] = useState(false)

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
        isUser
          ? 'bg-gradient-to-br from-blue-400 to-blue-600'
          : 'bg-gradient-to-br from-violet-500 to-purple-600'
      }`}>
        <span className="text-white text-xs font-bold">{isUser ? 'U' : 'AI'}</span>
      </div>
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        <div className={`inline-block max-w-[85%] text-left rounded-xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-slate-50 border border-slate-200'
        }`}>
          {isUser ? (
            <>
              {message.content && <p className="whitespace-pre-wrap">{message.content}</p>}
              {message.attachments && message.attachments.length > 0 && (
                <div className={`flex flex-wrap gap-1 ${message.content ? 'mt-2' : ''}`}>
                  {message.attachments.map((att, i) => (
                    <AttachmentChip key={i} attachment={att} />
                  ))}
                </div>
              )}
            </>
          ) : (
            <MarkdownViewer content={message.content} />
          )}
        </div>
        {!isUser && message.created_files && message.created_files.length > 0 && (
          <CreatedFilesBar files={message.created_files} />
        )}
        {!isUser && message.progress_events && message.progress_events.length > 0 && (
          <div className="mt-1.5">
            <button
              onClick={() => setProgressOpen(!progressOpen)}
              className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              {progressOpen ? 'Hide' : 'Show'} {message.progress_events.length} tool calls
            </button>
            {progressOpen && <ProgressEvents events={message.progress_events} />}
          </div>
        )}
      </div>
    </div>
  )
}

function CreatedFilesBar({ files }: { files: CreatedFile[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {files.map((file, i) => (
        <CreatedFileChip key={i} file={file} />
      ))}
    </div>
  )
}

function CreatedFileChip({ file }: { file: CreatedFile }) {
  const handleDownload = () => {
    if (!file.downloadable) return
    api.chatDownload(file.path)
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border ${
        file.downloadable
          ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
          : 'bg-slate-50 border-slate-200 text-slate-400'
      }`}
    >
      {file.downloadable ? (
        <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ) : (
        <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      )}
      <span className="truncate max-w-[160px]">{file.name}</span>
      {file.size != null && (
        <span className="text-[10px] opacity-60">({formatFileSize(file.size)})</span>
      )}
      {file.downloadable ? (
        <button
          onClick={handleDownload}
          className="ml-0.5 p-0.5 rounded hover:bg-emerald-100 transition-colors"
          title="Download"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
      ) : (
        <span className="text-[10px]">(restricted)</span>
      )}
    </span>
  )
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
// TaskFilesPanel — category-based file browser
// ---------------------------------------------------------------------------

interface TaskFilesPanelProps {
  taskFiles: TaskFilesResponse | null
  taskId: string
  onRefresh: () => void
  onFileReference: (filePath: string) => void
  onImagePreview: (url: string) => void
}

function TaskFilesPanel({ taskFiles, taskId, onRefresh, onFileReference, onImagePreview }: TaskFilesPanelProps) {
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

function ProgressEvents({ events }: { events: ChatProgressEvent[] }) {
  return (
    <div className="mt-2 space-y-0.5">
      {events.map((ev, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className="text-slate-300">{'>'}</span>
          {ev.tool && <span className="font-medium text-slate-500">{ev.tool}:</span>}
          <span className="truncate">{ev.detail}</span>
        </div>
      ))}
    </div>
  )
}
