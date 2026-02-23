import { useEffect, useRef, useCallback } from 'react'
import type { AnalysisJob } from '../types'

export type WSMessage =
  | { type: 'job_started'; job_id: string; job: AnalysisJob }
  | { type: 'output'; job_id: string; line: string }
  | { type: 'progress'; job_id: string; event: string; tool?: string; detail?: string; subtype?: string; duration_ms?: number; num_turns?: number; cost_usd?: number; timestamp?: string }
  | { type: 'job_finished'; job_id: string; job: AnalysisJob }

export function useWebSocket(onMessage: (msg: WSMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const onMessageRef = useRef(onMessage)

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/api/analysis/ws`)

    ws.onopen = () => console.log('[WS] connected')
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        onMessageRef.current(msg)
      } catch (e) {
        console.error('[WS] parse error:', e)
      }
    }
    ws.onclose = () => {
      console.log('[WS] disconnected, reconnecting in 3s...')
      reconnectTimer.current = setTimeout(connect, 3000)
    }
    ws.onerror = () => ws.close()

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { send }
}
