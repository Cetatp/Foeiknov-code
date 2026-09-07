/**
 * App — DeepSeek 风格蓉游智体 PandaAgent
 *
 * 布局：左侧 Sidebar（会话历史）+ 右侧主区（欢迎页 / 聊天）
 * 多会话管理：localStorage 持久化
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { Toast, Spin } from '@douyinfe/semi-ui'
import Sidebar, { loadConversations, saveConversations } from './components/Sidebar'
import ChatInput, { MODES } from './components/ChatInput'
import MessageBubble from './components/MessageBubble'
import { streamChat, fetchHealth } from './api/chatApi'
import './App.css'

function genId() {
  return `s_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function createConversation() {
  return {
    id: genId(),
    title: '新对话',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}

export default function App() {
  const [conversations, setConversations] = useState(() => loadConversations())
  const [activeId, setActiveId] = useState(() => {
    const list = loadConversations()
    return list[0]?.id || null
  })
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState('fast')
  const [deepThink, setDeepThink] = useState(false)
  const [smartSearch, setSmartSearch] = useState(false)
  const cancelRef = useRef(null)
  const bottomRef = useRef(null)

  const activeConv = conversations.find((c) => c.id === activeId)
  const messages = activeConv?.messages || []

  // 持久化会话列表
  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  // 自动滚动
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 更新当前会话
  const updateActiveConv = useCallback(
    (updater) => {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeId ? { ...updater(c), updatedAt: Date.now() } : c
        )
      )
    },
    [activeId]
  )

  // 新对话
  const handleNewChat = useCallback(() => {
    cancelRef.current?.()
    const conv = createConversation()
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
    setLoading(false)
  }, [])

  // 选择会话
  const handleSelect = useCallback((id) => {
    cancelRef.current?.()
    setActiveId(id)
    setLoading(false)
  }, [])

  // 删除会话
  const handleDelete = useCallback(
    (id) => {
      cancelRef.current?.()
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id)
        // 如果删除的是当前活动会话，切换到第一个
        if (id === activeId) {
          setActiveId(next[0]?.id || null)
          setLoading(false)
        }
        return next
      })
    },
    [activeId]
  )

  // 发送消息
  const handleSend = useCallback(
    (payload) => {
      const { text } = typeof payload === 'string' ? { text: payload } : payload
      const opts = typeof payload === 'object' ? payload : {}
      const sendMode = opts.mode || mode
      const sendDeepThink = opts.deepThink ?? deepThink
      const sendSmartSearch = opts.smartSearch ?? smartSearch
      const sendImage = opts.image || null  // { dataUrl, name }

      if (loading) return
      // 若无活动会话，自动创建
      let convId = activeId
      if (!convId) {
        const conv = createConversation()
        convId = conv.id
        setConversations((prev) => [conv, ...prev])
        setActiveId(conv.id)
      }

      const userMsg = { role: 'user', content: text, structures: [], image: sendImage }
      const agentMsg = { role: 'assistant', content: '', structures: [], reasoning: '', streaming: true }

      // 标题取首条用户消息（有文字用文字，没文字用图片名）
      const title = text ? text.slice(0, 20) : (sendImage?.name || '图片')

      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                title: c.messages.length === 0 ? title : c.title,
                messages: [...c.messages, userMsg, agentMsg],
                updatedAt: Date.now(),
              }
            : c
        )
      )
      setLoading(true)

      const updateLast = (updater) => {
        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== convId) return c
            const msgs = [...c.messages]
            msgs[msgs.length - 1] = updater(msgs[msgs.length - 1])
            return { ...c, messages: msgs, updatedAt: Date.now() }
          })
        )
      }

      const cancel = streamChat(text, convId, {
        mode: sendMode,
        deep_think: sendDeepThink,
        smart_search: sendSmartSearch,
        image: sendImage?.dataUrl || null,
        onToken: (chunk) => {
          updateLast((m) => ({ ...m, content: m.content + chunk }))
        },
        onReasoning: (text) => {
          updateLast((m) => ({ ...m, reasoning: (m.reasoning || '') + text }))
        },
        onStructure: (type, payload) => {
          updateLast((m) => ({
            ...m,
            structures: [...m.structures, { type, payload }],
          }))
        },
        onEnd: (finalAnswer) => {
          updateLast((m) => ({
            ...m,
            content: finalAnswer || m.content,
            streaming: false,
          }))
          setLoading(false)
        },
        onError: (err) => {
          updateLast((m) => ({
            ...m,
            content: `❌ 请求失败：${err.message}`,
            streaming: false,
          }))
          Toast.error(`对话出错：${err.message}`)
          setLoading(false)
        },
      })

      cancelRef.current = cancel
    },
    [activeId, loading, mode, deepThink, smartSearch]
  )

  const hasMessages = messages.length > 0

  return (
    <div className="ds-app">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNewChat}
        onDelete={handleDelete}
      />

      <main className="ds-main">
        {hasMessages ? (
          <>
            <div className="ds-chat-scroll">
              <div className="ds-chat-inner">
                {messages.map((msg, idx) => (
                  <MessageBubble key={idx} message={msg} />
                ))}
                {loading && (
                  <div className="ds-loading">
                    <div className="ds-loading-bubble">
                      <span>🐼 正在思考中</span>
                      <span className="ds-loading-dots">
                        <span /><span /><span />
                      </span>
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </div>
            <div className="ds-chat-input-area">
              <ChatInput
                onSend={handleSend}
                loading={loading}
                mode={mode}
                deepThink={deepThink}
                smartSearch={smartSearch}
                onModeChange={setMode}
                onDeepThinkChange={setDeepThink}
                onSmartSearchChange={setSmartSearch}
              />
              <div className="ds-footer-tip">蓉游智体可能会出错，请核实重要信息</div>
            </div>
          </>
        ) : (
          <div className="ds-welcome">
            <div className="ds-welcome-logo">🐼</div>
            <h1 className="ds-welcome-title">今天想聊些什么？</h1>

            {/* 模式切换 */}
            <div className="ds-mode-tabs">
              {MODES.map((m) => (
                <button
                  key={m.key}
                  className={`ds-mode-tab ${mode === m.key ? 'active' : ''}`}
                  onClick={() => setMode(m.key)}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {/* 输入框 */}
            <div className="ds-welcome-input">
              <ChatInput
                onSend={handleSend}
                loading={loading}
                mode={mode}
                deepThink={deepThink}
                smartSearch={smartSearch}
                onModeChange={setMode}
                onDeepThinkChange={setDeepThink}
                onSmartSearchChange={setSmartSearch}
              />
            </div>

            {/* 快捷问题 */}
            <div className="ds-quick-questions">
              {[
                '大熊猫基地几点开门？门票多少钱？',
                '帮我做一个成都3天亲子游行程，人均预算6000',
                '熊猫基地附近有什么好吃的和景点？',
                '成都1天怎么玩？',
              ].map((q) => (
                <button
                  key={q}
                  className="ds-quick-q"
                  onClick={() => handleSend(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
