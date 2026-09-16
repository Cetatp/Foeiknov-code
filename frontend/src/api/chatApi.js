/**
 * SSE 聊天 API 封装
 */
import { SSE } from 'sse.js'

export function streamChat(message, sessionId, callbacks = {}) {
  const { onToken, onStructure, onEnd, onError } = callbacks

  const source = new SSE('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    payload: JSON.stringify({
      message,
      session_id: sessionId,
      stream: true,
    }),
    start: false,
  })

  source.addEventListener('token', (e) => {
    try {
      const data = JSON.parse(e.data)
      onToken?.(data.text || '')
    } catch (_) {}
  })

  source.addEventListener('structure_ready', (e) => {
    try {
      const data = JSON.parse(e.data)
      onStructure?.(data.type, data.payload)
    } catch (_) {}
  })

  source.addEventListener('end', (e) => {
    try {
      const data = JSON.parse(e.data)
      onEnd?.(data.final_answer || '', data.session_id)
    } catch (_) {
      onEnd?.('', sessionId)
    }
  })

  source.addEventListener('error', (e) => {
    onError?.(new Error(e?.data || 'SSE 连接错误'))
  })

  source.stream()

  return () => {
    try {
      source.close()
    } catch (_) {}
  }
}

export async function fetchSpots(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`/api/spots?${qs}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchSpotDetail(spotId) {
  const res = await fetch(`/api/spots/${spotId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchHealth() {
  const res = await fetch('/health')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
