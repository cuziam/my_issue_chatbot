import { useState, useEffect, useRef, useCallback } from 'react'
import type { ChatSession, ChatMessage } from '../types'
import type { WSMessage } from '../hooks/useWebSocket'
import { useWebSocket } from '../hooks/useWebSocket'
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

const NEW_SESSION = '__new__'

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
  const [historyLoading, setHistoryLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const processedChatIds = useRef<Set<string>>(new Set())

  useEffect(() => {
    const loadHistory = async () => {
      setHistoryLoading(true)
      try {
        const { messages: hist } = await api.chatHistory(taskId)
        setMessages(hist.map(m => ({
          ...m,
          role: m.role as 'user' | 'assistant',
        })))
      } catch {
        // No history yet
      } finally {
        setHistoryLoading(false)
      }
    }
    loadHistory()
  }, [taskId])

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

  const handleWsMessage = useCallback(
    (msg: WSMessage) => {
      if (msg.type === 'chat_response' && msg.task_id === taskId) {
        if (msg.done) {
          // Deduplicate: skip if this chat_id was already processed
          if (processedChatIds.current.has(msg.chat_id)) return
          processedChatIds.current.add(msg.chat_id)

          setMessages(prev => [
            ...prev,
            {
              role: 'assistant',
              content: msg.content,
              timestamp: new Date().toISOString(),
              progress_events: [...activeProgressEvents],
            },
          ])
          setStreamingContent('')
          setActiveProgressEvents([])
          setIsLoading(false)
          setActiveChatId(null)
        } else {
          setStreamingContent(msg.content)
        }
      } else if (msg.type === 'chat_progress' && msg.task_id === taskId) {
        setActiveProgressEvents(prev => [
          ...prev,
          { event: msg.event, tool: msg.tool, detail: msg.detail },
        ])
      }
    },
    [taskId, activeProgressEvents]
  )

  useWebSocket(handleWsMessage)

  const effectiveSessionId = selectedSession === NEW_SESSION ? null : selectedSession

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return

    const userMessage = inputText.trim()
    setInputText('')
    setIsLoading(true)
    setStreamingContent('')
    setActiveProgressEvents([])

    setMessages(prev => [
      ...prev,
      { role: 'user', content: userMessage, timestamp: new Date().toISOString() },
    ])

    try {
      const result = await api.chatSend(taskId, effectiveSessionId, userMessage)
      setActiveChatId(result.chat_id)
      if (result.is_new_session) {
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
    if (streamingContent) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: streamingContent + '\n\n*(cancelled)*', timestamp: new Date().toISOString() },
      ])
      setStreamingContent('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isNewChat = selectedSession === NEW_SESSION || selectedSession === null
  const placeholder = isNewChat
    ? 'Ask about this task... (Shift+Enter for new line)'
    : 'Ask a follow-up question... (Shift+Enter for new line)'

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

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
          {historyLoading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner size="md" />
            </div>
          ) : messages.length === 0 && !streamingContent ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400">
              <svg className="w-14 h-14 mb-4 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-base font-medium text-slate-500">Ask anything about this task</p>
              <p className="text-sm text-slate-400 mt-1">
                {isNewChat ? 'A new session will be created' : 'Full context from the selected session'}
              </p>
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
                    <div className="bg-slate-50 rounded-xl px-4 py-3 border border-slate-200 text-sm leading-relaxed">
                      <MarkdownViewer content={streamingContent} />
                    </div>
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

        {/* Input area */}
        <div className="px-5 py-4 border-t border-slate-200 bg-slate-50/50">
          <div className="flex gap-3 items-end">
            <textarea
              ref={textareaRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
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
                disabled={!inputText.trim()}
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
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <MarkdownViewer content={message.content} />
          )}
        </div>
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
