/**
 * SSE 聊天 API 封装
 *
 * 使用 sse.js（EventSourcePolyfill）实现 POST + SSE 流式消费。
 * 原生 EventSource 只支持 GET，无法 POST 大段消息。
 *
 * 返回一个 Promise，resolve 时拿到完整 final_answer；
 * 同时通过 onToken / onStructure / onEnd 回调做渐进渲染。
 */
import { SSE } from 'sse.js'

/**
 * 发起 SSE 流式聊天
 * @param {string} message 用户消息
 * @param {string} sessionId 会话 ID
 * @param {object} opts 选项
 * @param {string} opts.mode 运行模式 fast|expert|vision
 * @param {boolean} opts.deep_think 是否深度思考
 * @param {boolean} opts.smart_search 是否智能搜索
 * @param {string|null} opts.image 图片 base64 dataURL（识图模式）
 * @param {object} callbacks 回调集合
 * @param {(text: string) => void} callbacks.onToken 增量 token
 * @param {(text: string) => void} callbacks.onReasoning 深度思考过程
 * @param {(type: string, payload: any) => void} callbacks.onStructure 结构化卡片
 * @param {(answer: string, sessionId: string) => void} callbacks.onEnd 最终答案
 * @param {(error: Error) => void} callbacks.onError 错误
 * @returns {() => void} 取消函数
 */
export function streamChat(message, sessionId, opts = {}) {
  const { mode = 'fast', deep_think = false, smart_search = false, image = null, ...callbacks } = opts
  const { onToken, onReasoning, onStructure, onEnd, onError } = callbacks

  const source = new SSE('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    payload: JSON.stringify({
      message,
      session_id: sessionId,
      stream: true,
      mode,
      deep_think,
      smart_search,
      image,
    }),
    start: false,
  })

  // 监听各事件类型
  source.addEventListener('token', (e) => {
    try {
      const data = JSON.parse(e.data)
      onToken?.(data.text || '')
    } catch (_) {}
  })

  // ★ 深度思考过程
  source.addEventListener('reasoning', (e) => {
    try {
      const data = JSON.parse(e.data)
      onReasoning?.(data.text || '')
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

  // 启动流
  source.stream()

  // 返回取消函数
  return () => {
    try {
      source.close()
    } catch (_) {}
  }
}

/**
 * 查询景点列表
 */
export async function fetchSpots(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`/api/spots?${qs}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * 查询景点详情
 */
export async function fetchSpotDetail(spotId) {
  const res = await fetch(`/api/spots/${spotId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * 健康检查
 */
export async function fetchHealth() {
  const res = await fetch('/health')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
