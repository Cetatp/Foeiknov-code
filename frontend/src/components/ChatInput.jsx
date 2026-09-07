/**
 * ChatInput — DeepSeek 风格输入框
 *
 * - 大圆角容器，自动撑高
 * - 底部：功能标签（深度思考/智能搜索）+ 附件 + 蓝色发送按钮
 */
import { useState, useRef, useEffect } from 'react'
import { IconSend, IconPaperclip, IconClose } from '@douyinfe/semi-icons'

const MODES = [
  { key: 'fast', label: '⚡ 快速模式' },
  { key: 'expert', label: '◇ 专家模式' },
  { key: 'vision', label: '🖼 识图模式' },
]

export default function ChatInput({ onSend, loading, mode, deepThink, smartSearch, onModeChange, onDeepThinkChange, onSmartSearchChange }) {
  const [value, setValue] = useState('')
  const [image, setImage] = useState(null)  // { dataUrl, name }
  const taRef = useRef(null)
  const fileInputRef = useRef(null)

  // 自动高度
  useEffect(() => {
    const ta = taRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
    }
  }, [value])

  // 选择图片
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setImage({ dataUrl: reader.result, name: file.name })
    }
    reader.readAsDataURL(file)
    e.target.value = ''  // 重置，允许重复选同一张
  }

  const handleSend = () => {
    const text = value.trim()
    // 有图片或有文字都可以发送
    if ((!text && !image) || loading) return
    onSend({ text, mode, deepThink, smartSearch, image })
    setValue('')
    setImage(null)
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
        {/* 图片预览 */}
        {image && (
          <div className="ds-image-preview">
            <img src={image.dataUrl} alt={image.name} />
            <button
              className="ds-image-remove"
              onClick={() => setImage(null)}
              title="移除图片"
            >
              <IconClose size="small" />
            </button>
          </div>
        )}
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
          <div className="ds-input-tags">
            <button
              className={`ds-tag ${deepThink ? 'active' : ''}`}
              onClick={() => onDeepThinkChange?.(!deepThink)}
            >
              ⚙ 深度思考
            </button>
            <button
              className={`ds-tag ${smartSearch ? 'active' : ''}`}
              onClick={() => onSmartSearchChange?.(!smartSearch)}
            >
              🔍 智能搜索
            </button>
          </div>
          <div className="ds-input-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <button
              className="ds-attach-btn"
              title="上传图片"
              onClick={() => fileInputRef.current?.click()}
            >
              <IconPaperclip size="large" />
            </button>
            <button
              className={`ds-send-btn ${(value.trim() || image) && !loading ? '' : 'disabled'}`}
              onClick={handleSend}
              disabled={(!value.trim() && !image) || loading}
            >
              <IconSend size="large" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export { MODES }
