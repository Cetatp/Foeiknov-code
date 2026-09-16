"""
景点查询路由 — GET /api/spots, GET /api/spots/{spot_id}

支持关键词模糊搜索、级别/区域过滤、分页。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.database.mysql_client import engine
from app.schemas.api_models import SpotBrief, SpotDetail, SpotListResponse

router = APIRouter(prefix="/api", tags=["spots"])


@router.get("/spots", response_model=SpotListResponse)
async def list_spots(
    keyword: Optional[str] = Query(default=None, description="关键词模糊匹配 spot_name/address"),
    spot_level: Optional[str] = Query(default=None, description="级别过滤：5A/4A/3A"),
    area_tag: Optional[str] = Query(default=None, description="区域过滤：成华区/武侯区..."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    景点列表查询。

    - 1554 条景点数据，支持关键词搜索和多条件过滤
    - 默认返回前 20 条，limit 最大 200
    """
    conditions = []
    params = {}

    if keyword:
        conditions.append("(spot_name LIKE :kw OR address LIKE :kw)")
        params["kw"] = f"%{keyword}%"
    if spot_level:
        conditions.append("spot_level = :level")
        params["level"] = spot_level
    if area_tag:
        conditions.append("area_tag = :area")
        params["area"] = area_tag

    where = " AND ".join(conditions) if conditions else "1=1"

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM spots WHERE {where}"), params
        ).scalar()

        rows = conn.execute(
            text(f"""
                SELECT spot_id, spot_name, spot_level, address,
                       longitude, latitude, rating, ticket_price_min, area_tag
                FROM spots
                WHERE {where}
                ORDER BY rating DESC, spot_level DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": limit, "offset": offset},
        ).fetchall()

    items = [
        SpotBrief(
            spot_id=r[0],
            spot_name=r[1],
            spot_level=r[2],
            address=r[3],
            longitude=float(r[4]) if r[4] is not None else None,
            latitude=float(r[5]) if r[5] is not None else None,
            rating=float(r[6]) if r[6] is not None else None,
            ticket_price_min=r[7],
            area_tag=r[8],
        )
        for r in rows
    ]
    return SpotListResponse(total=total, items=items)


@router.get("/spots/{spot_id}", response_model=SpotDetail)
async def get_spot(spot_id: int):
    """
    单个景点详情（含 description / travel_tips / cultural_context）。
    """
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM spots WHERE spot_id = :id"),
            {"id": spot_id},
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"景点 {spot_id} 不存在")

    d = dict(row._mapping)
    return SpotDetail(
        spot_id=d["spot_id"],
        spot_name=d["spot_name"],
        spot_level=d.get("spot_level"),
        address=d.get("address"),
        longitude=float(d["longitude"]) if d.get("longitude") is not None else None,
        latitude=float(d["latitude"]) if d.get("latitude") is not None else None,
        rating=float(d["rating"]) if d.get("rating") is not None else None,
        ticket_price_min=d.get("ticket_price_min"),
        area_tag=d.get("area_tag"),
        description=d.get("description"),
        travel_tips=d.get("travel_tips"),
        cultural_context=d.get("cultural_context"),
        avg_visit_hours=float(d["avg_visit_hours"]) if d.get("avg_visit_hours") is not None else None,
    )
