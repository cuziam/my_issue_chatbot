import { createContext, useContext, useEffect, useRef, useCallback, type ReactNode } from 'react'
import type { AnalysisJob } from '../types'

export type WSMessage =
  | { type: 'job_started'; job_id: string; job: AnalysisJob }
  | { type: 'output'; job_id: string; line: string }
  | { type: 'progress'; job_id: string; event: string; tool?: string; detail?: string; subtype?: string; duration_ms?: number; num_turns?: number; cost_usd?: number; timestamp?: string }
  | { type: 'job_finished'; job_id: string; job: AnalysisJob }
  | { type: 'mode_resolved'; job_id: string; resolved_mode: string }
  // Chat messages
  | { type: 'chat_output'; chat_id: string; task_id: string; line: string }
  | { type: 'chat_progress'; chat_id: string; task_id: string; event: string; tool?: string; detail?: string; timestamp?: string }
  | { type: 'chat_response'; chat_id: string; task_id: string; content: string; done: boolean }

type Subscriber = (msg: WSMessage) => void

interface WSContextValue {
  subscribe: (fn: Subscriber) => () => void
  send: (data: unknown) => void
}

const WebSocketContext = createContext<WSContextValue | null>(null)

/**
 * App-level WebSocket provider.
 * Maintains a single WebSocket connection shared across all pages.
 * Pages subscribe/unsubscribe via useWebSocket() hook — no duplicate connections.
 */
export function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null)
  const subscribersRef = useRef<Set<Subscriber>>(new Set())
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    // Prevent connecting if unmounted or already connected/connecting
    if (!mountedRef.current) return
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/api/analysis/ws`)

    ws.onopen = () => console.log('[WS] connected (singleton)')

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage
        subscribersRef.current.forEach((fn) => fn(msg))
      } catch (e) {
        console.error('[WS] parse error:', e)
      }
    }

    ws.onclose = () => {
      console.log('[WS] disconnected')
      wsRef.current = null
      if (mountedRef.current) {
        reconnectTimer.current = setTimeout(connect, 3000)
      }
    }

    ws.onerror = () => ws.close()
    wsRef.current = ws
  }, [])

  // Single connection on app mount
  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const subscribe = useCallback((fn: Subscriber) => {
    subscribersRef.current.add(fn)
    return () => { subscribersRef.current.delete(fn) }
  }, [])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const value: WSContextValue = { subscribe, send }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

/**
 * Subscribe to WebSocket messages from the singleton connection.
 * Safe to call from any page — no new connection is created.
 */
export function useWebSocketContext(onMessage: (msg: WSMessage) => void) {
  const ctx = useContext(WebSocketContext)
  const onMessageRef = useRef(onMessage)
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])

  useEffect(() => {
    if (!ctx) return
    const handler: Subscriber = (msg) => onMessageRef.current(msg)
    return ctx.subscribe(handler)
  }, [ctx])

  return { send: ctx?.send ?? (() => {}) }
}
