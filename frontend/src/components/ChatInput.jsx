/**
 * ChatInput — 单一默认模式输入框
 */
import { useState, useRef, useEffect } from 'react'
import { IconSend } from '@douyinfe/semi-icons'

export default function ChatInput({ onSend, loading }) {
  const [value, setValue] = useState('')
  const taRef = useRef(null)

  useEffect(() => {
    const ta = taRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
    }
  }, [value])

  const handleSend = () => {
    const text = value.trim()
    if (!text || loading) return
    onSend(text)
    setValue('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="ds-input-wrap">
      <div className="ds-input-box">
        <textarea
          ref={taRef}
          className="ds-textarea"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="给蓉游智体发送消息"
          rows={1}
          disabled={loading}
        />
        <div className="ds-input-bottom">
          <div />
          <div className="ds-input-actions">
            <button
              className={`ds-send-btn ${value.trim() && !loading ? '' : 'disabled'}`}
              onClick={handleSend}
              disabled={!value.trim() || loading}
            >
              <IconSend size="large" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
