import { useState, useEffect, useRef, useCallback } from 'react'
import type { ChatSession, ChatMessage, TaskFilesResponse } from '../../types'
import type { WSMessage } from '../../hooks/useWebSocket'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useImageLightbox } from '../../contexts/ImageLightboxContext'
import { api } from '../../api/client'
import LoadingSpinner from '../LoadingSpinner'
import ChatMessageItem, { StreamingMessage } from './ChatMessageItem'
import type { ChatProgressEvent, PendingFile } from './ChatMessageItem'
import ChatInput from './ChatInput'
import ChatFileList from './ChatFileList'
import { formatFileSize } from './ChatFileList'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  taskId: string
  sessions: ChatSession[]
  onSessionCreated?: () => void
  open: boolean
  onClose: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NEW_SESSION = '__new__'
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

// ---------------------------------------------------------------------------
// ChatPanel — main container with WebSocket/streaming/state
// ---------------------------------------------------------------------------

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
  const [activeCreatedFiles, setActiveCreatedFiles] = useState<import('../../types').CreatedFile[]>([])
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
    // (skipNextHistoryLoadRef is true when handleSend triggers session change -- don't clear)
    if (!skipNextHistoryLoadRef.current) {
      activeChatIdRef.current = null
    }
  }, [effectiveSessionId])

  // Load history when task or session changes -- backend filters by session_id
  useEffect(() => {
    // Don't load for "New Chat Session" -- starts empty
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

  // -------------------------------------------------------------------------
  // WebSocket handler
  // -------------------------------------------------------------------------

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

  // -------------------------------------------------------------------------
  // File handling
  // -------------------------------------------------------------------------

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

  // -------------------------------------------------------------------------
  // Send / Cancel
  // -------------------------------------------------------------------------

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
        // Skip history load -- optimistic msg already in state, streaming via WS
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

  // -------------------------------------------------------------------------
  // Derived state
  // -------------------------------------------------------------------------

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

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

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
                  <ChatMessageItem key={idx} message={msg} />
                ))}
                <StreamingMessage
                  streamingContent={streamingContent}
                  activeProgressEvents={activeProgressEvents}
                  activeCreatedFiles={activeCreatedFiles}
                  isLoading={isLoading}
                />
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Files panel */}
          {filesOpen && (
            <ChatFileList
              taskFiles={taskFiles}
              taskId={taskId}
              onRefresh={loadTaskFiles}
              onFileReference={handleFileReference}
              onImagePreview={openLightbox}
            />
          )}
        </div>

        {/* Input area (includes file preview bar) */}
        <ChatInput
          inputText={inputText}
          onInputChange={setInputText}
          onSend={handleSend}
          onCancel={handleCancel}
          onFiles={handleFiles}
          onRemoveFile={removePendingFile}
          pendingFiles={pendingFiles}
          uploadingCount={uploadingCount}
          isLoading={isLoading}
          isDragOver={isDragOver}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          placeholder={placeholder}
          canSend={canSend}
          textareaRef={textareaRef}
          fileInputRef={fileInputRef}
        />
      </div>
    </div>
  )
}
