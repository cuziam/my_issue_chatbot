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
}

interface ProgressEvent {
  event: string
  tool?: string
  detail?: string
}

export default function ChatPanel({ taskId, sessions, onSessionCreated }: ChatPanelProps) {
  // "__new__" means new chat, otherwise session_id string
  const [selectedSession, setSelectedSession] = useState<string | null>(
    sessions.length > 0 ? sessions[0].session_id : null
  )
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [streamingContent, setStreamingContent] = useState('')
  const [activeProgressEvents, setActiveProgressEvents] = useState<ProgressEvent[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load chat history
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

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // WebSocket handler for chat events
  const handleWsMessage = useCallback(
    (msg: WSMessage) => {
      if (msg.type === 'chat_response' && msg.task_id === taskId) {
        if (msg.done) {
          // Finalize: add assistant message to history
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
          // Streaming partial content
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

  // Effective session_id: null for new chat, string for existing
  const effectiveSessionId = selectedSession === '__new__' ? null : selectedSession

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return

    const userMessage = inputText.trim()
    setInputText('')
    setIsLoading(true)
    setStreamingContent('')
    setActiveProgressEvents([])

    // Add user message immediately
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

  const handleSessionChange = (value: string) => {
    if (value === '__new__') {
      setSelectedSession('__new__')
    } else {
      setSelectedSession(value)
    }
  }

  const isNewChat = selectedSession === '__new__' || selectedSession === null
  const placeholder = isNewChat
    ? 'Ask about this task (new session will be created)...'
    : 'Ask a follow-up question...'

  return (
    <div className="flex flex-col h-[600px]">
      {/* Session selector */}
      <div className="flex items-center gap-3 pb-3 border-b border-slate-200 mb-3">
        <label className="text-xs font-medium text-slate-500">Session:</label>
        <select
          value={selectedSession === null ? '__new__' : selectedSession}
          onChange={(e) => handleSessionChange(e.target.value)}
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="__new__">+ New Chat Session</option>
          {sessions.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {s.source === 'chat' ? 'chat' : s.mode} - {s.job_id.substring(0, 8)} ({s.status})
              {s.started_at ? ` - ${new Date(s.started_at).toLocaleDateString()}` : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {historyLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner size="md" />
          </div>
        ) : messages.length === 0 && !streamingContent ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400">
            {isNewChat ? (
              <>
                <svg className="w-10 h-10 mb-3 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p className="text-sm">Ask anything about this task</p>
                <p className="text-xs text-slate-300 mt-1">A new session will be created with task context</p>
              </>
            ) : (
              <>
                <p className="text-sm">Start a conversation about this analysis</p>
                <p className="text-xs text-slate-300 mt-1">The AI will have full context from the selected session</p>
              </>
            )}
          </div>
        ) : (
          <>
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} />
            ))}
            {/* Streaming response */}
            {streamingContent && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-white text-[10px] font-bold">AI</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="bg-slate-50 rounded-xl px-4 py-3 border border-slate-200">
                    <MarkdownViewer content={streamingContent} />
                  </div>
                  {activeProgressEvents.length > 0 && (
                    <ProgressEvents events={activeProgressEvents} />
                  )}
                </div>
              </div>
            )}
            {/* Loading indicator */}
            {isLoading && !streamingContent && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-[10px] font-bold">AI</span>
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
      <div className="pt-3 border-t border-slate-200 mt-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder={placeholder}
            disabled={isLoading}
            className="flex-1 border border-slate-200 rounded-lg px-4 py-2.5 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
          />
          {isLoading ? (
            <button
              onClick={handleCancel}
              className="px-4 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium transition-colors flex items-center gap-2"
            >
              Cancel
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!inputText.trim()}
              className="px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              Send
            </button>
          )}
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
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
        isUser
          ? 'bg-gradient-to-br from-blue-400 to-blue-600'
          : 'bg-gradient-to-br from-violet-500 to-purple-600'
      }`}>
        <span className="text-white text-[10px] font-bold">{isUser ? 'U' : 'AI'}</span>
      </div>
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        <div className={`inline-block max-w-full text-left rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-slate-50 border border-slate-200'
        }`}>
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <MarkdownViewer content={message.content} />
          )}
        </div>
        {/* Progress events (collapsible) */}
        {!isUser && message.progress_events && message.progress_events.length > 0 && (
          <div className="mt-1">
            <button
              onClick={() => setProgressOpen(!progressOpen)}
              className="text-xs text-slate-400 hover:text-slate-600"
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

function ProgressEvents({ events }: { events: ProgressEvent[] }) {
  return (
    <div className="mt-1.5 space-y-0.5">
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
