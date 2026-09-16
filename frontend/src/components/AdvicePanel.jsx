/**
 * AdvicePanel — 六维建议面板
 *
 * 接收后端 advice_worker 的 structure_ready payload，
 * 用 Semi Tabs 展示 6 个维度：天气 / 预算 / 交通 / 避坑 / 美食 / 拍照。
 */
import { Tabs, Card, Typography, Space } from '@douyinfe/semi-ui'

const { Text, Title } = Typography

// 六维建议的图标和颜色
const ADVICE_TABS = [
  { key: 'weather', label: '🌤️ 天气' },
  { key: 'budget', label: '💰 预算' },
  { key: 'transport', label: '🚇 交通' },
  { key: 'pitfalls', label: '⚠️ 避坑' },
  { key: 'food', label: '🍜 美食' },
  { key: 'photo', label: '📸 拍照' },
]

function parseAdvice(payload) {
  if (typeof payload === 'string') return { raw: payload }
  if (payload && typeof payload === 'object') {
    return payload
  }
  return { raw: JSON.stringify(payload, null, 2) }
}

function renderContent(content) {
  if (!content) return <Text type="tertiary">暂无建议</Text>
  if (typeof content === 'string') {
    return (
      <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7 }}>{content}</div>
    )
  }
  if (Array.isArray(content)) {
    return (
      <ul style={{ paddingLeft: 20, fontSize: 13, lineHeight: 1.9 }}>
        {content.map((item, i) => (
          <li key={i}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
        ))}
      </ul>
    )
  }
  return <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(content, null, 2)}</pre>
}

export default function AdvicePanel({ payload }) {
  const advice = parseAdvice(payload)

  if (advice.raw) {
    return (
      <Card style={{ margin: '8px 0' }} bodyStyle={{ padding: 12 }}>
        <Title heading={5} style={{ margin: 0, marginBottom: 8 }}>
          💡 实用建议
        </Title>
        <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13 }}>{advice.raw}</pre>
      </Card>
    )
  }

  return (
    <Card style={{ margin: '8px 0' }} bodyStyle={{ padding: 12 }}>
      <Space vertical align="start" style={{ width: '100%' }}>
        <Title heading={5} style={{ margin: 0 }}>
          💡 实用建议（六维）
        </Title>
        <Tabs type="line" style={{ width: '100%' }}>
          {ADVICE_TABS.map((tab) => {
            const content = advice[tab.key]
            const hasContent = content && (typeof content !== 'string' || content.length > 0)
            return (
              <Tabs.TabPane
                key={tab.key}
                tab={
                  <span>
                    {tab.label}
                    {hasContent ? null : <span style={{ opacity: 0.4 }}> (空)</span>}
                  </span>
                }
                itemKey={tab.key}
              >
                {renderContent(content)}
              </Tabs.TabPane>
            )
          })}
        </Tabs>
      </Space>
    </Card>
  )
}
