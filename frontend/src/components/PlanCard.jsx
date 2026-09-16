import { Card, Typography, Tag } from '@douyinfe/semi-ui'
const { Text, Title } = Typography

function parsePlan(payload) {
  // dict payload 直接返回
  if (payload && !Array.isArray(payload) && typeof payload === 'object') {
    if (Array.isArray(payload.days)) {
      return { days: payload.days, title: payload.title, budget: payload.total_budget, rules: payload.rules_applied }
    }
    if (payload.error) {
      return { error: payload.error }
    }
  }
  // 数组 payload → 当作 days
  if (Array.isArray(payload)) {
    return { days: payload }
  }
  return { error: '无法解析行程数据' }
}

function renderSpot(spot) {
  if (!spot) return null
  if (typeof spot === 'string') return spot
  // { spot_name, time, desc } 格式
  const parts = []
  if (spot.time) parts.push(`⏰ ${spot.time}`)
  if (spot.spot_name) parts.push(spot.spot_name)
  if (spot.desc) parts.push(spot.desc)
  return parts.join(' · ')
}

export default function PlanCard({ payload }) {
  const plan = parsePlan(payload)

  if (plan.error) {
    return (
      <Card style={{ margin: '8px 0' }} bodyStyle={{ padding: 12 }}>
        <Text type="tertiary">{plan.error}</Text>
      </Card>
    )
  }

  return (
    <Card className="ds-structure-card ds-plan-card" style={{ margin: '8px 0' }} bodyStyle={{ padding: 0 }}>
      <div className="ds-plan-header">
        <span className="ds-plan-emoji">📋</span>
        <Text strong style={{ fontSize: 14 }}>
          {plan.title || '行程规划'}
        </Text>
        {plan.budget != null && (
          <Tag color="blue" size="small">预算 ¥{plan.budget}</Tag>
        )}
        {plan.rules?.length > 0 && (
          <Tag color="green" size="small">硬规则 {plan.rules.length}条</Tag>
        )}
      </div>
      <div className="ds-plan-days">
        {plan.days?.map((day, idx) => (
          <div key={idx} className="ds-plan-day">
            <div className="ds-plan-day-header">
              <span className="ds-plan-day-num">Day {day.day || idx + 1}</span>
              {day.transit_minutes != null && (
                <Text type="tertiary" size="small">🚶 {day.transit_minutes}min</Text>
              )}
              {day.budget != null && (
                <Text type="tertiary" size="small">💰 ¥{day.budget}</Text>
              )}
            </div>
            <div className="ds-plan-timeline">
              {day.morning && (
                <div className="ds-plan-slot ds-plan-morning">
                  <span className="ds-plan-slot-label">☀️ 上午</span>
                  <span className="ds-plan-slot-content">{renderSpot(day.morning)}</span>
                </div>
              )}
              {day.afternoon && (
                <div className="ds-plan-slot ds-plan-afternoon">
                  <span className="ds-plan-slot-label">🌤️ 下午</span>
                  <span className="ds-plan-slot-content">{renderSpot(day.afternoon)}</span>
                </div>
              )}
              {day.evening && (
                <div className="ds-plan-slot ds-plan-evening">
                  <span className="ds-plan-slot-label">🌙 晚上</span>
                  <span className="ds-plan-slot-content">{renderSpot(day.evening)}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
