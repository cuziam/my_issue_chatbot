/**
 * Re-export from WebSocketContext for backwards compatibility.
 * All pages share a single WebSocket connection via the App-level provider.
 */
export type { WSMessage } from '../contexts/WebSocketContext'
export { useWebSocketContext as useWebSocket } from '../contexts/WebSocketContext'
