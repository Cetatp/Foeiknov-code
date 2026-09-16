"""
数据库 ORM 模型（9 张表）
spots / foods / food_shops / avoid_rules / hard_rules / transit_matrix /
chat_sessions(记忆冷备) / user_profiles(LTM硬槽位) / dlq(死信队列)
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, Integer,
    Numeric, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.dialects.mysql import JSON, MEDIUMTEXT

from app.database.mysql_client import Base


class Spot(Base):
    """景点表（1554 条，覆盖成都全部区县）"""
    __tablename__ = "spots"

    spot_id = Column(Integer, primary_key=True, autoincrement=True)
    spot_name = Column(String(128), nullable=False, comment="景点名称")
    spot_level = Column(String(16), comment="等级：5A/4A/3A/-")
    poi_category = Column(String(64), comment="POI 分类")
    address = Column(String(256), comment="地址")
    longitude = Column(Numeric(10, 7), comment="经度")
    latitude = Column(Numeric(10, 7), comment="纬度")
    rating = Column(Numeric(3, 1), comment="评分 0-5")
    ticket_price_min = Column(Integer, comment="最低门票价格（元）")
    opening_hours_json = Column(JSON, comment="开放时间 JSON：{open, close}")
    description = Column(Text, comment="景点描述")
    travel_tips = Column(Text, comment="游玩建议")
    cultural_context = Column(Text, comment="文化背景")
    avg_visit_hours = Column(Numeric(3, 1), comment="平均游览时长（小时）")
    area_tag = Column(String(32), comment="所属区县")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_spots_name", "spot_name"),
        Index("idx_spots_area", "area_tag"),
        Index("idx_spots_location", "longitude", "latitude"),
    )


class Food(Base):
    """美食表（80 道，覆盖 8 大类）"""
    __tablename__ = "foods"

    food_id = Column(Integer, primary_key=True, autoincrement=True)
    food_name = Column(String(64), nullable=False, comment="美食名称")
    category = Column(String(32), comment="分类：火锅/串串/小吃/川菜/凉菜/甜品...")
    description = Column(Text, comment="描述")
    avg_price = Column(String(32), comment="人均价格区间")
    best_areas = Column(String(256), comment="推荐区域")
    famous_shops = Column(String(256), comment="知名店铺")

    __table_args__ = (
        Index("idx_foods_category", "category"),
    )


class FoodShop(Base):
    """美食店铺表（1624 家）"""
    __tablename__ = "food_shops"

    shop_id = Column(Integer, primary_key=True, autoincrement=True)
    shop_name = Column(String(128), nullable=False, comment="店铺名称")
    category = Column(String(64), comment="美食分类")
    address = Column(String(256), comment="地址")
    longitude = Column(Numeric(10, 7), comment="经度")
    latitude = Column(Numeric(10, 7), comment="纬度")
    tel = Column(String(128), comment="电话")
    rating = Column(Numeric(3, 1), comment="评分")
    cost = Column(Numeric(8, 2), comment="人均价格（元）")
    business_area = Column(String(64), comment="所属商圈/区县")
    type = Column(String(128), comment="类型")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_food_shops_category", "category"),
        Index("idx_food_shops_area", "business_area"),
        Index("idx_food_shops_location", "longitude", "latitude"),
        Index("idx_food_shops_rating", "rating"),
    )


class AvoidRule(Base):
    """避坑规则表（250 条，覆盖 10 大场景）"""
    __tablename__ = "avoid_rules"

    rule_id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(32), comment="场景分类")
    title = Column(String(128), comment="规则标题")
    content = Column(Text, comment="规则内容")
    severity = Column(Enum("high", "medium", "low"), comment="严重程度")

    __table_args__ = (
        Index("idx_avoid_rules_severity", "severity"),
    )


class HardRule(Base):
    """硬规则表（53 条，含 R-001~R-008 程序级强制规则）"""
    __tablename__ = "hard_rules"

    rule_id = Column(String(16), primary_key=True, comment="规则编号 R-001~R-053")
    rule_content = Column(Text, nullable=False, comment="规则内容")
    reason = Column(Text, comment="规则原因")
    priority = Column(Integer, comment="优先级（数字越小越高）")


class TransitMatrix(Base):
    """通勤矩阵表（190157 条，1554 景点 100% 双向覆盖）"""
    __tablename__ = "transit_matrix"

    matrix_id = Column(BigInteger, primary_key=True, autoincrement=True)
    from_spot_id = Column(Integer, nullable=False, comment="起点景点 ID")
    from_spot_name = Column(String(128), comment="起点景点名称")
    to_spot_id = Column(Integer, nullable=False, comment="终点景点 ID")
    to_spot_name = Column(String(128), comment="终点景点名称")
    transit_mode = Column(Enum("driving", "transit", "walking"), comment="交通方式")
    duration_min = Column(Integer, comment="通勤时长（分钟）")
    distance_km = Column(Numeric(8, 2), comment="距离（公里）")
    same_region = Column(Boolean, default=False, comment="是否同区域")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("from_spot_id", "to_spot_id", "transit_mode", name="uk_transit_pair_mode"),
        Index("idx_transit_from", "from_spot_id"),
        Index("idx_transit_to", "to_spot_id"),
    )


class ChatSession(Base):
    """会话记忆冷备表（不参与在线读，仅故障回源/审计）"""
    __tablename__ = "chat_sessions"

    session_id = Column(String(64), primary_key=True, comment="会话 ID = thread_id")
    user_id = Column(String(64), index=True, comment="用户 ID")
    messages = Column(JSON, comment="完整对话快照")
    window_tokens = Column(Integer, default=0, comment="近似 Token 数，Rolling Summary 触发依据")
    summary_blob = Column(MEDIUMTEXT, comment="更早对话的语义摘要")
    last_summary_at = Column(DateTime, comment="最近一次压缩时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_chat_sessions_user", "user_id", "updated_at"),
    )


class UserProfile(Base):
    """LTM 长期用户画像硬槽位（finalize_prompt 查表 100% 注入 System）"""
    __tablename__ = "user_profiles"

    user_id = Column(String(64), primary_key=True, default="local_user", comment="用户 ID")
    group_type = Column(Enum("solo", "couple", "family", "friends", "business", "senior"), comment="出行人群")
    budget_level = Column(Enum("budget", "standard", "comfort", "luxury"), comment="预算等级")
    pace = Column(Enum("relaxed", "moderate", "packed"), comment="行程节奏")
    allergies_json = Column(JSON, comment="忌口/黑名单")
    must_include_json = Column(JSON, comment="必去景点")
    must_exclude_json = Column(JSON, comment="黑名单景点/品类")
    notes = Column(Text, comment="自由备注")
    ltm_chunk_count = Column(Integer, default=0, comment="累计 LTM 提取次数")
    ltm_last_extract_at = Column(DateTime, comment="最近一次 LTM 提取时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeadLetter(Base):
    """死信队列表（异步归档/LTM 抽取失败兜底）"""
    __tablename__ = "dlq"

    dlq_id = Column(BigInteger, primary_key=True, autoincrement=True)
    phase = Column(Enum("archive", "ltm_extract", "notify"), comment="失败阶段")
    biz_key = Column(String(128), comment="业务键：session_id / user_id")
    payload_json = Column(JSON, comment="原 state / profile 快照")
    error_msg = Column(Text, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    next_retry_at = Column(DateTime, comment="下次重试时间")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_dlq_phase_retry", "phase", "next_retry_at"),
    )
