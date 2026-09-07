/**
 * NearbyList — 周边推荐列表
 *
 * 接收后端 nearby_worker 的 structure_ready payload，
 * 用 Semi List + Rating + 距离 Badge + 交通信息渲染。
 */
import { List, Card, Rating, Tag, Typography, Space, Avatar } from '@douyinfe/semi-ui'
import { IconMapPin, IconClock } from '@douyinfe/semi-icons'

const { Text, Title } = Typography

function parseNearby(payload) {
  // 情况1: { items: [...] } — 直接取 items
  if (payload && Array.isArray(payload.items)) return { items: payload.items }
  // 情况2: [...] — 直接就是数组
  if (Array.isArray(payload)) return { items: payload }
  // 情况3: { name, distance_km, rating } — 单个对象包装成数组
  if (payload && payload.name) return { items: [payload] }
  // 兜底
  return { items: [] }
}

function getDistanceBadge(item) {
  // 兼容 distance_km / distance / distance_m 三种字段
  let dist = item.distance_km ?? item.distance
  if (dist == null) return null
  const km = typeof dist === 'number' ? dist : parseFloat(dist)
  if (isNaN(km)) return null
  const text = km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`
  const color = km < 1 ? 'green' : km < 3 ? 'blue' : 'grey'
  return (
    <Tag color={color} icon={<IconMapPin />} size="small">
      {text}
    </Tag>
  )
}

export default function NearbyList({ payload }) {
  const nearby = parseNearby(payload)

  if (nearby.items.length === 0) {
    return (
      <Card style={{ margin: '8px 0' }} bodyStyle={{ padding: 12 }}>
        <Text type="tertiary">暂无周边推荐</Text>
      </Card>
    )
  }

  return (
    <Card className="ds-structure-card ds-nearby-card" style={{ margin: '8px 0' }} bodyStyle={{ padding: 0 }}>
      <div className="ds-nearby-header">
        <span className="ds-nearby-emoji">📍</span>
        <Text strong style={{ fontSize: 14 }}>
          周边推荐 <Text type="tertiary" size="small">({nearby.items.length}个)</Text>
        </Text>
      </div>
      <div className="ds-nearby-list">
        {nearby.items.map((item, idx) => (
          <div key={idx} className="ds-nearby-item">
            <div className="ds-nearby-rank">{idx + 1}</div>
            <div className="ds-nearby-info">
              <div className="ds-nearby-name-row">
                <Text strong style={{ fontSize: 14 }}>
                  {item.name || item.spot_name || '未知景点'}
                </Text>
                {getDistanceBadge(item)}
                {item.spot_level && <Tag size="small">{item.spot_level}</Tag>}
              </div>
              <div className="ds-nearby-meta">
                {item.rating != null && (
                  <span className="ds-nearby-rating">
                    ⭐ {item.rating}
                  </span>
                )}
                {item.address && (
                  <Text type="tertiary" size="small" icon={<IconMapPin />}>
                    {item.address}
                  </Text>
                )}
              </div>
              {item.travel_time && (
                <div className="ds-nearby-travel">
                  <IconClock size="small" />
                  <Text type="tertiary" size="small">{item.travel_time}</Text>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
