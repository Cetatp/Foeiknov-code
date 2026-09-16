/**
 * QACard — 问答卡片（RAG 检索增强）
 *
 * 接收后端 qa_worker 的 structure_ready payload，
 * 展示答案 + 引用出处。
 */
import { Card, Typography, Space } from '@douyinfe/semi-ui'
import CitationTag from './CitationTag'

const { Text, Title } = Typography

function parseQA(payload) {
  if (typeof payload === 'string') return { raw: payload }
  if (payload && typeof payload === 'object') {
    return {
      answer: payload.answer || payload.summary || '',
      citations: payload.citations || payload.sources || [],
    }
  }
  return { raw: JSON.stringify(payload, null, 2) }
}

export default function QACard({ payload }) {
  const qa = parseQA(payload)

  if (qa.raw) {
    return (
      <Card style={{ margin: '8px 0' }} bodyStyle={{ padding: 12 }}>
        <Title heading={5} style={{ margin: 0, marginBottom: 8 }}>
          📖 知识库问答
        </Title>
        <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13 }}>{qa.raw}</pre>
      </Card>
    )
  }

  return (
    <Card style={{ margin: '8px 0' }} bodyStyle={{ padding: 12 }}>
      <Space vertical align="start" style={{ width: '100%' }}>
        <Space>
          <Title heading={5} style={{ margin: 0 }}>
            📖 知识库问答
          </Title>
          <CitationTag citations={qa.citations} />
        </Space>
        {qa.answer ? (
          <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8 }}>
            {qa.answer}
          </div>
        ) : (
          <Text type="tertiary">（答案由下方总结提供）</Text>
        )}
      </Space>
    </Card>
  )
}
