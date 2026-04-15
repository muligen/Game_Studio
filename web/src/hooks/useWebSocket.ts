import { useEffect, useRef, useState } from 'react'

type WebSocketMessage = {
  type: string
  [key: string]: any
}

type WebSocketHook = {
  connected: boolean
  subscribe: (workspace: string) => void
  unsubscribe: () => void
}

export function useWebSocket(): WebSocketHook {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number>()

  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

      ws.onopen = () => {
        setConnected(true)
        console.log('WebSocket connected')
      }

      ws.onclose = () => {
        setConnected(false)
        console.log('WebSocket disconnected, reconnecting...')
        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, 3000)
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data) as WebSocketMessage
        console.log('WebSocket message:', message)

        // Emit custom event for components to listen to
        window.dispatchEvent(new CustomEvent('ws-message', { detail: message }))
      }

      wsRef.current = ws
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const subscribe = (workspace: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        workspace,
      }))
    }
  }

  const unsubscribe = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'unsubscribe',
      }))
    }
  }

  return { connected, subscribe, unsubscribe }
}
