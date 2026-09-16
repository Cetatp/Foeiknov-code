/**
 * Sidebar — DeepSeek 风格左侧会话栏
 *
 * - Logo + 搜索/历史图标
 * - 开启新对话按钮
 * - 会话历史按日期分组（今天/昨天/7天内）
 */
import { IconSearch, IconHistory, IconDelete } from '@douyinfe/semi-icons'

const STORAGE_KEY = 'chengdu_conversations'

/** 从 localStorage 读取会话列表 */
export function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

/** 保存会话列表 */
export function saveConversations(list) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(0, 100)))
}

/** 按日期分组 */
function groupByDate(conversations) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups = { 今天: [], 昨天: [], '7天内': [], 更早: [] }

  conversations.forEach((c) => {
    const d = new Date(c.updatedAt || c.createdAt || Date.now())
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    if (day >= today) groups['今天'].push(c)
    else if (day >= yesterday) groups['昨天'].push(c)
    else if (day >= weekAgo) groups['7天内'].push(c)
    else groups['更早'].push(c)
  })

  return groups
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}) {
  const groups = groupByDate(conversations)

  return (
    <aside className="ds-sidebar">
      {/* 顶部 Logo 区 */}
      <div className="ds-sidebar-top">
        <div className="ds-logo">
          <span className="ds-logo-icon">🐼</span>
          <span className="ds-logo-text">蓉游智体 · PandaAgent</span>
        </div>
        <div className="ds-sidebar-icons">
          <button className="ds-icon-btn" title="搜索">
            <IconSearch size="large" />
          </button>
          <button className="ds-icon-btn" title="历史记录">
            <IconHistory size="large" />
          </button>
        </div>
      </div>

      {/* 新对话按钮 */}
      <button className="ds-new-chat-btn" onClick={onNew}>
        <span className="ds-new-chat-plus">＋</span>
        开启新对话
      </button>

      {/* 会话列表 */}
      <nav className="ds-conv-list">
        {Object.entries(groups).map(([label, items]) =>
          items.length > 0 ? (
            <div key={label} className="ds-conv-group">
              <div className="ds-conv-group-label">{label}</div>
              {items.map((c) => (
                <div
                  key={c.id}
                  className={`ds-conv-item ${c.id === activeId ? 'active' : ''}`}
                  onClick={() => onSelect(c.id)}
                  title={c.title}
                >
                  <span className="ds-conv-title">{c.title || '新对话'}</span>
                  {onDelete && (
                    <button
                      className="ds-conv-delete"
                      title="删除对话"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDelete(c.id)
                      }}
                    >
                      <IconDelete size="small" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : null
        )}
        {conversations.length === 0 && (
          <div className="ds-conv-empty">暂无历史对话</div>
        )}
      </nav>
    </aside>
  )
}
