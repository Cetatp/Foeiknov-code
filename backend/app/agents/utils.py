"""
Agent 工具函数 — Haversine 距离 / 行程硬规则校验 / 安全 JSON 解析
"""
import math
import json
import copy
import datetime
from typing import Any


# ── Haversine 距离计算（经纬度→公里）──
def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算两点间球面距离（公里）。"""
    R = 6371.0  # 地球半径 km
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ── 安全 JSON 解析 ──
def safe_json_loads(text: str, default: Any = None) -> Any:
    """安全解析 JSON，失败返回 default。"""
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        # 尝试提取第一个 {...} 块
        if "{" in text and "}" in text:
            start = text.index("{")
            end = text.rindex("}") + 1
            try:
                return json.loads(text[start:end])
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return default


# ── 行程硬规则程序级强制校验（R-001 ~ R-008）──
def validate_plan(plan: dict) -> dict:
    """
    程序级强制 R-001~R-008，与 Prompt 注入形成双保险。
    在 plan["rules_applied"] 中记录每条规则的执行情况。
    """
    if not isinstance(plan, dict):
        return plan

    plan = copy.deepcopy(plan)  # ★ 深拷贝，避免修改入参

    if "rules_applied" not in plan:
        plan["rules_applied"] = []

    days = plan.get("days", [])
    if not days:
        return plan

    # ── R-002：都江堰+青城山必须同一天，不与市区景点混排 ──
    for i, day in enumerate(days):
        spots = [
            str(day.get(slot, {}).get("spot_name", ""))
            for slot in ["morning", "afternoon", "evening"]
            if day.get(slot)
        ]
        has_djq = any("都江堰" in s or "青城山" in s for s in spots)
        has_urban = any(
            any(k in s for k in ["宽窄", "锦里", "春熙", "太古", "武侯祠", "杜甫草堂"])
            for s in spots
        )
        if has_djq and has_urban:
            plan["rules_applied"].append(f"R-002(violated:day{i+1}都江堰与市区混排)")

    # ── R-003：武侯祠+锦里必须同半天（一墙之隔）──
    for i, day in enumerate(days):
        for slot in ["morning", "afternoon"]:
            slot_spot = str(day.get(slot, {}).get("spot_name", ""))
            if "武侯祠" in slot_spot or "锦里" in slot_spot:
                other = "afternoon" if slot == "morning" else "morning"
                other_spot = str(day.get(other, {}).get("spot_name", ""))
                if ("武侯祠" in slot_spot and "锦里" not in other_spot) or \
                   ("锦里" in slot_spot and "武侯祠" not in other_spot):
                    plan["rules_applied"].append(
                        f"R-003(violated:day{i+1}.{slot}武侯祠/锦里未同半天)"
                    )

    # ── R-004：杜甫草堂+金沙遗址同半天（车程15分钟）──
    for i, day in enumerate(days):
        for slot in ["morning", "afternoon"]:
            slot_spot = str(day.get(slot, {}).get("spot_name", ""))
            if "杜甫草堂" in slot_spot or "金沙" in slot_spot:
                other = "afternoon" if slot == "morning" else "morning"
                other_spot = str(day.get(other, {}).get("spot_name", ""))
                if ("杜甫草堂" in slot_spot and "金沙" not in other_spot) or \
                   ("金沙" in slot_spot and "杜甫草堂" not in other_spot):
                    plan["rules_applied"].append(
                        f"R-004(violated:day{i+1}.{slot}杜甫草堂/金沙未同半天)"
                    )

    # ── R-005：金沙遗址/四川博物院周一闭馆 ──
    start_date = plan.get("start_date")
    if start_date:
        try:
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            for i, day in enumerate(days):
                if (start + datetime.timedelta(days=i)).weekday() == 0:  # 周一
                    spots = [
                        str(day.get(slot, {}).get("spot_name", ""))
                        for slot in ["morning", "afternoon", "evening"]
                        if day.get(slot)
                    ]
                    if any("金沙" in s or "四川博物院" in s or "川博" in s for s in spots):
                        plan["rules_applied"].append(
                            f"R-005(violated:day{i+1}周一安排金沙/川博)"
                        )
        except ValueError:
            pass

    # ── R-006：每日景点不超过 3 个（统计所有时段 slot）──
    reserved_keys = {"day", "transit_minutes", "budget", "date"}
    for i, day in enumerate(days):
        slot_keys = [k for k in day.keys() if k not in reserved_keys and isinstance(day.get(k), dict)]
        spot_count = sum(1 for k in slot_keys if day[k].get("spot_name"))
        if spot_count > 3:
            plan["rules_applied"].append(
                f"R-006(violated:day{i+1}={spot_count}景点>3)"
            )

    # ── R-007：每日通勤总时间不超过 3 小时 ──
    for i, day in enumerate(days):
        transit = day.get("transit_minutes", 0)
        if isinstance(transit, (int, float)) and transit > 180:
            plan["rules_applied"].append(
                f"R-007(violated:day{i+1}通勤{transit}分钟>180)"
            )

    # ── R-008：亲子/老人团避免高海拔（西岭雪山 3000m+）──
    group = str(plan.get("group_type", ""))
    if group in ("亲子", "老人", "家庭", "带小孩", "带老人"):
        for i, day in enumerate(days):
            spots = [
                str(day.get(slot, {}).get("spot_name", ""))
                for slot in ["morning", "afternoon", "evening"]
                if day.get(slot)
            ]
            if any("西岭雪山" in s for s in spots):
                plan["rules_applied"].append(
                    f"R-008(violated:day{i+1}亲子/老人团安排西岭雪山)"
                )

    # ── R-001：熊猫基地必须在 Day1 上午（最后执行，强制覆盖，保留原安排）──
    day1_morning = days[0].get("morning", {}) if days else {}
    morning_spot = str(day1_morning.get("spot_name", ""))
    if "熊猫" not in morning_spot and "大熊猫" not in morning_spot:
        # 保留原安排到备注，避免用户意图丢失
        original_spot = morning_spot if morning_spot else "（无安排）"
        days[0]["morning"] = {
            "spot_name": "成都大熊猫繁育研究基地",
            "time": "08:00-12:00",
            "reason": "R-001: 熊猫上午最活跃，必须 Day1 上午",
            "original_spot": original_spot,  # ★ 记录被覆盖的原景点
        }
        # 如果下午为空，把原景点挪到下午；否则仅记录
        day1_afternoon = days[0].get("afternoon", {})
        if not day1_afternoon.get("spot_name") and original_spot != "（无安排）":
            days[0]["afternoon"] = {
                "spot_name": original_spot,
                "time": "13:00-17:00",
                "desc": "原 Day1 上午安排，因 R-001 调整至下午",
            }
        plan["rules_applied"].append(
            f"R-001(forced:熊猫基地→Day1上午, 原安排[{original_spot}]已移至下午或备注)"
        )

    return plan
