/**
 * CitationTag — 引用出处标签 [↑n]
 *
 * 渲染 QA Worker 返回的 citations 引用，可点击展开 snippet 预览。
 */
import { useState } from 'react'
import { Popover, Tag, Typography } from '@douyinfe/semi-ui'

const { Text } = Typography

export default function CitationTag({ citations }) {
  const [open, setOpen] = useState(false)

  if (!citations || citations.length === 0) return null

  const content = (
    <div style={{ maxWidth: 320 }}>
      {citations.map((c, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <Text strong>{c.source || `来源 ${i + 1}`}</Text>
          {c.score != null && (
            <Text type="tertiary" style={{ fontSize: 11, marginLeft: 8 }}>
              相似度 {(c.score * 100).toFixed(1)}%
            </Text>
          )}
          <div
            style={{
              fontSize: 12,
              lineHeight: 1.6,
              marginTop: 4,
              maxHeight: 80,
              overflow: 'auto',
              background: 'var(--semi-color-fill-0)',
              padding: 6,
              borderRadius: 4,
            }}
          >
            {c.snippet || c.text || '(无摘要)'}
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <Popover
      content={content}
      trigger="click"
      visible={open}
      onVisibleChange={setOpen}
    >
      <Tag
        color="blue"
        style={{ cursor: 'pointer', marginLeft: 4 }}
        onClick={() => setOpen(!open)}
      >
        ↑{citations.length}
      </Tag>
    </Popover>
  )
}
