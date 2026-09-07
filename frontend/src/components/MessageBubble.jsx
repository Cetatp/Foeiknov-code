/**
 * MessageBubble — 融合豆包 + DeepSeek 风格的消息气泡
 *
 * 后端 _clean_markdown 保留了：## 标题、- 列表、1. 列表、| 表格、> 引用、emoji、○ 子项、空行
 * 前端解析器支持：表格 / 嵌套列表 / 引用块 / emoji 标题 / 导语段落
 */
import { Collapse } from '@douyinfe/semi-ui'
import { IconBulb } from '@douyinfe/semi-icons'
import PlanCard from './PlanCard'
import AdvicePanel from './AdvicePanel'
import NearbyList from './NearbyList'
import QACard from './QACard'

/** 隐式标题关键词 */
const HEADER_KEYWORDS = /行程|时间|门票|交通|建议|贴士|提醒|攻略|注意|提示|亮点|介绍|文化|历史|美食|住宿|周边|串联|天气|穿衣|装备|避坑|拍照|须知|指南|小贴士|温馨提示|基础信息|开放时间|游玩建议|交通方式|游览建议|周边推荐|票价|预约|实用|核心|必看|路线|地址|游玩|注意事项|开放/

/**
 * 解析表格：从 header 行（| a | b |）和 separator 行（| --- | --- |）开始，
 * 收集后续所有以 | 开头的行作为数据行。
 */
function parseTable(lines, startIdx) {
  const headerLine = lines[startIdx]
  if (!headerLine || !/^\s*\|/.test(headerLine)) return null

  // 分隔线行（|---|---|）必须紧跟 header 之后
  const sepLine = lines[startIdx + 1]
  if (!sepLine || !/^\s*\|[\s\-:|]+\|?\s*$/.test(sepLine)) return null

  const headers = headerLine.split('|').map(c => c.trim()).filter((_, i, a) => !(i === 0 && a[0] === '') && !(i === a.length - 1 && a[a.length - 1] === ''))
  const rows = []
  let j = startIdx + 2
  while (j < lines.length && /^\s*\|/.test(lines[j])) {
    const cells = lines[j].split('|').map(c => c.trim()).filter((_, i, a) => !(i === 0 && a[0] === '') && !(i === a.length - 1 && a[a.length - 1] === ''))
    if (cells.length === headers.length) rows.push(cells)
    j++
  }
  return { headers, rows, endIdx: j }
}

/**
 * 解析嵌套列表：- 顶层 item，○ 作为二级子项
 */
function parseListItem(line, indentLevel) {
  // ○ / ● / ▸ 作为子项符号
  const subMatch = line.match(/^(\s*)(○|●|▸|▫|·)\s*(.+)$/)
  if (subMatch) {
    return { level: 1, text: subMatch[3].trim(), indent: subMatch[1].length }
  }
  // - / * / • 作为主项
  const mainMatch = line.match(/^(\s*)[-*•]\s+(.+)$/)
  if (mainMatch) {
    return { level: 0, text: mainMatch[2].trim(), indent: mainMatch[1].length }
  }
  return null
}

function parseMarkdown(text) {
  if (!text) return []
  const lines = text.split('\n')
  const blocks = []
  let i = 0

  while (i < lines.length) {
    const rawLine = lines[i]
    const trimmed = rawLine.trim()

    if (!trimmed) { i++; continue }

    // 1. 表格（| 开头）
    if (/^\s*\|/.test(trimmed)) {
      const table = parseTable(lines, i)
      if (table) {
        blocks.push({ type: 'table', headers: table.headers, rows: table.rows })
        i = table.endIdx
        continue
      }
    }

    // 2. ## / ### 标题
    const hMatch = trimmed.match(/^(#{1,3})\s+(.+)$/)
    if (hMatch) {
      const level = hMatch[1].length
      blocks.push({ type: 'heading', level, text: hMatch[2].trim() })
      i++
      continue
    }

    // 3. > 引用块
    const quoteMatch = trimmed.match(/^>\s*(.+)$/)
    if (quoteMatch) {
      // 收集连续的引用行
      const items = [quoteMatch[1]]
      i++
      while (i < lines.length) {
        const nm = lines[i].trim().match(/^>\s*(.+)$/)
        if (nm) { items.push(nm[1]); i++ }
        else break
      }
      blocks.push({ type: 'quote', text: items.join(' ') })
      continue
    }

    // 4. 嵌套列表（主项 + 可选子项）
    if (/^\s*[-*•]\s+/.test(trimmed) || /^\s*○\s+/.test(trimmed)) {
      const topItems = []
      let currentMain = null
      let currentSubs = []

      while (i < lines.length) {
        const line = lines[i]
        const item = parseListItem(line)
        if (!item) break

        if (item.level === 0) {
          // 保存上一个主项及其子项
          if (currentMain) {
            topItems.push({ text: currentMain, subs: currentSubs })
          }
          currentMain = item.text
          currentSubs = []
        } else {
          // 子项
          currentSubs.push(item.text)
        }
        i++
      }
      if (currentMain) {
        topItems.push({ text: currentMain, subs: currentSubs })
      }
      blocks.push({ type: 'ul', items: topItems })
      continue
    }

    // 5. 有序列表
    const olMatch = trimmed.match(/^\d+[.、]\s*(.+)$/)
    if (olMatch) {
      const items = [olMatch[1]]
      i++
      while (i < lines.length) {
        const nm = lines[i].trim().match(/^\d+[.、]\s*(.+)$/)
        if (nm) { items.push(nm[1]); i++ }
        else break
      }
      blocks.push({ type: 'ol', items })
      continue
    }

    // 6. 隐式标题：短行 + 无标点结尾 + 包含标题关键词
    if (trimmed.length <= 20 && !/[。？！,，]$/.test(trimmed) && HEADER_KEYWORDS.test(trimmed)) {
      blocks.push({ type: 'heading', level: 2, text: trimmed })
      i++
      continue
    }

    // 7. 普通段落（可能是导语）
    const paraLines = [trimmed]
    i++
    while (i < lines.length) {
      const next = lines[i].trim()
      if (!next) break
      // 遇到结构化元素则停止
      if (/^#{1,3}\s/.test(next)) break
      if (/^\s*\|/.test(next)) break
      if (/^>\s/.test(next)) break
      if (/^\s*[-*•]\s+/.test(next) || /^\s*○\s+/.test(next)) break
      if (/^\d+[.、]\s/.test(next)) break
      // 隐式标题
      if (next.length <= 20 && !/[。？！,，]$/.test(next) && HEADER_KEYWORDS.test(next)) break
      paraLines.push(next)
      i++
    }
    const text = paraLines.join(' ')
    blocks.push({ type: 'paragraph', text })
  }

  return blocks
}

/**
 * 渲染 Markdown blocks 为 JSX
 */
function renderMarkdown(text) {
  const blocks = parseMarkdown(text)
  if (blocks.length === 0) return null

  return blocks.map((block, i) => {
    if (block.type === 'heading') {
      return (
        <div key={i} className={`ds-md ds-md-heading ds-md-h${block.level}`}>
          <span className="ds-md-heading-bar" />
          <span className="ds-md-heading-text">{block.text}</span>
        </div>
      )
    }

    if (block.type === 'table') {
      return (
        <div key={i} className="ds-md-table-wrap">
          <table className="ds-md-table">
            <thead>
              <tr>
                {block.headers.map((h, j) => <th key={j}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, j) => (
                <tr key={j}>
                  {row.map((cell, k) => <td key={k}>{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    if (block.type === 'quote') {
      return (
        <div key={i} className="ds-md-quote">
          <span className="ds-md-quote-bar" />
          <span className="ds-md-quote-text">{block.text}</span>
        </div>
      )
    }

    if (block.type === 'ol') {
      return (
        <ol key={i} className="ds-md ds-md-ol">
          {block.items.map((item, j) => <li key={j}>{item}</li>)}
        </ol>
      )
    }

    if (block.type === 'ul') {
      return (
        <ul key={i} className="ds-md ds-md-ul">
          {block.items.map((item, j) => (
            <li key={j}>
              {item.text}
              {item.subs && item.subs.length > 0 && (
                <ul className="ds-md ds-md-ul ds-md-ul-nested">
                  {item.subs.map((sub, k) => <li key={k} className="ds-md-sub-item">{sub}</li>)}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )
    }

    // paragraph
    return <p key={i} className="ds-md ds-md-p">{block.text}</p>
  })
}

function renderStructure(type, payload) {
  switch (type) {
    case 'plan_card':
    case 'plan':
      return <PlanCard payload={payload} />
    case 'advice_panel':
    case 'advice':
      return <AdvicePanel payload={payload} />
    case 'nearby_list':
    case 'nearby':
      return <NearbyList payload={payload} />
    case 'qa_card':
    case 'qa':
      return <QACard payload={payload} />
    default:
      return null
  }
}

export default function MessageBubble({ message }) {
  const { role, content, structures = [], reasoning = '', streaming, image } = message
  const isUser = role === 'user'

  if (isUser) {
    return (
      <div className="ds-msg ds-msg-user">
        {image && image.dataUrl && (
          <div className="ds-user-image">
            <img src={image.dataUrl} alt={image.name || 'upload'} />
          </div>
        )}
        {content && <div className="ds-user-bubble">{content}</div>}
      </div>
    )
  }

  return (
    <div className="ds-msg ds-msg-agent">
      <div className="ds-agent-avatar">🐼</div>
      <div className="ds-agent-content">
        {/* 深度思考过程（可折叠） */}
        {reasoning && (
          <div className="ds-reasoning">
            <Collapse>
              <Collapse.Panel
                header={
                  <span className="ds-reasoning-header">
                    <IconBulb size="small" style={{ marginRight: 6 }} />
                    深度思考过程
                  </span>
                }
                itemKey="reasoning"
              >
                <div className="ds-reasoning-text">{reasoning}</div>
              </Collapse.Panel>
            </Collapse>
          </div>
        )}
        {structures.map((s, i) => (
          <div key={i} className="ds-structure-card">
            {renderStructure(s.type, s.payload)}
          </div>
        ))}
        {content && (
          <div className="ds-agent-text">
            {renderMarkdown(content)}
            {streaming && <span className="ds-cursor" />}
          </div>
        )}
      </div>
    </div>
  )
}
