/**
 * App — 蓉游智体 PandaAgent
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { Toast } from '@douyinfe/semi-ui'
import Sidebar, { loadConversations, saveConversations } from './components/Sidebar'
import ChatInput from './components/ChatInput'
import MessageBubble from './components/MessageBubble'
import { streamChat } from './api/chatApi'
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
  const cancelRef = useRef(null)
  const bottomRef = useRef(null)

  const activeConv = conversations.find((c) => c.id === activeId)
  const messages = activeConv?.messages || []

  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleNewChat = useCallback(() => {
    cancelRef.current?.()
    const conv = createConversation()
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
    setLoading(false)
  }, [])

  const handleSelect = useCallback((id) => {
    cancelRef.current?.()
    setActiveId(id)
    setLoading(false)
  }, [])

  const handleDelete = useCallback((id) => {
    cancelRef.current?.()
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id)
      if (id === activeId) {
        setActiveId(next[0]?.id || null)
        setLoading(false)
      }
      return next
    })
  }, [activeId])

  const handleSend = useCallback((text) => {
    if (!text || loading) return

    let convId = activeId
    if (!convId) {
      const conv = createConversation()
      convId = conv.id
      setConversations((prev) => [conv, ...prev])
      setActiveId(conv.id)
    }

    const userMsg = { role: 'user', content: text, structures: [] }
    const agentMsg = { role: 'assistant', content: '', structures: [], streaming: true }
    const title = text.slice(0, 20)

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
      onToken: (chunk) => {
        updateLast((m) => ({ ...m, content: m.content + chunk }))
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
  }, [activeId, loading])

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
                      <span>🐼 正在处理中</span>
                      <span className="ds-loading-dots"><span /><span /><span /></span>
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </div>
            <div className="ds-chat-input-area">
              <ChatInput onSend={handleSend} loading={loading} />
              <div className="ds-footer-tip">蓉游智体可能会出错，请核实重要信息</div>
            </div>
          </>
        ) : (
          <div className="ds-welcome">
            <div className="ds-welcome-logo">🐼</div>
            <h1 className="ds-welcome-title">今天想聊些什么？</h1>

            <div className="ds-welcome-input">
              <ChatInput onSend={handleSend} loading={loading} />
            </div>

            <div className="ds-quick-questions">
              {[
                '大熊猫基地几点开门？门票多少钱？',
                '帮我做一个成都3天亲子游行程，人均预算6000',
                '熊猫基地附近有什么景点？',
                '成都1天怎么玩？',
              ].map((q) => (
                <button key={q} className="ds-quick-q" onClick={() => handleSend(q)}>
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
