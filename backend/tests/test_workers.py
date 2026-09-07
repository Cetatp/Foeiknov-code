"""
Worker 工具函数与输出结构测试

不依赖 LLM API，测试：
- haversine 距离计算
- safe_json_loads 安全解析
- validate_plan 硬规则 R-001~R-008
- merge_results reducer
"""
import sys
sys.path.insert(0, ".")

import pytest
from app.agents.utils import haversine, safe_json_loads, validate_plan
from app.schemas.agent_models import merge_results


# ── Haversine 距离 ──
class TestHaversine:
    def test_same_point(self):
        assert haversine(104.0, 30.6, 104.0, 30.6) == 0.0

    def test_known_distance(self):
        # 成都到重庆约 270km
        dist = haversine(104.0668, 30.5728, 106.5516, 29.5630)
        assert 260 < dist < 290

    def test_nearby_spots(self):
        # 宽窄巷子到人民公园约 1km
        dist = haversine(104.0612, 30.6721, 104.0637, 30.6692)
        assert 0 < dist < 5


# ── 安全 JSON 解析 ──
class TestSafeJson:
    def test_valid_json(self):
        assert safe_json_loads('{"a": 1}') == {"a": 1}

    def test_invalid_json(self):
        assert safe_json_loads("not json", default={}) == {}

    def test_extract_json_block(self):
        text = '好的，结果如下：{"next_workers": ["qa_worker"]} 希望对你有帮助'
        assert safe_json_loads(text) == {"next_workers": ["qa_worker"]}

    def test_empty(self):
        assert safe_json_loads("", default=None) is None


# ── merge_results reducer ──
class TestMergeResults:
    def test_merge_two_dicts(self):
        left = {"qa": "a"}
        right = {"plan": "b"}
        assert merge_results(left, right) == {"qa": "a", "plan": "b"}

    def test_right_overrides_left(self):
        left = {"qa": "a"}
        right = {"qa": "b"}
        assert merge_results(left, right) == {"qa": "b"}

    def test_empty_left(self):
        assert merge_results({}, {"qa": "a"}) == {"qa": "a"}

    def test_none_left(self):
        assert merge_results(None, {"qa": "a"}) == {"qa": "a"}


# ── validate_plan 硬规则 R-001~R-008 ──
class TestValidatePlan:
    def test_r001_panda_day1_morning(self):
        """R-001: 熊猫基地必须 Day1 上午"""
        plan = {
            "days": [
                {"morning": {"spot_name": "宽窄巷子"}, "afternoon": {"spot_name": "锦里"}}
            ]
        }
        result = validate_plan(plan)
        day1_morning = result["days"][0]["morning"]["spot_name"]
        assert "熊猫" in day1_morning or "大熊猫" in day1_morning
        assert any("R-001" in r for r in result["rules_applied"])

    def test_r001_already_panda(self):
        """R-001: 已有熊猫基地则不强制"""
        plan = {
            "days": [
                {"morning": {"spot_name": "成都大熊猫繁育研究基地"}, "afternoon": {}}
            ]
        }
        result = validate_plan(plan)
        assert not any("R-001(forced" in r for r in result["rules_applied"])

    def test_r002_dujiangyan_urban_mix(self):
        """R-002: 都江堰不与市区混排（Day2，避免 R-001 干扰）"""
        plan = {
            "days": [
                {"morning": {"spot_name": "成都大熊猫繁育研究基地"}, "afternoon": {"spot_name": "宽窄巷子"}},
                {"morning": {"spot_name": "都江堰"}, "afternoon": {"spot_name": "春熙路"}},
            ]
        }
        result = validate_plan(plan)
        assert any("R-002" in r for r in result["rules_applied"])

    def test_r003_wuhouci_jinli_same_half(self):
        """R-003: 武侯祠+锦里同半天（Day2，避免 R-001 干扰）"""
        plan = {
            "days": [
                {"morning": {"spot_name": "成都大熊猫繁育研究基地"}, "afternoon": {}},
                {"morning": {"spot_name": "武侯祠"}, "afternoon": {"spot_name": "春熙路"}},
            ]
        }
        result = validate_plan(plan)
        assert any("R-003" in r for r in result["rules_applied"])

    def test_r006_daily_spots_limit(self):
        """R-006: 每日不超过 3 个景点"""
        plan = {
            "days": [
                {
                    "morning": {"spot_name": "A"},
                    "afternoon": {"spot_name": "B"},
                    "evening": {"spot_name": "C"},
                }
            ]
        }
        result = validate_plan(plan)
        # 3 个不违规
        assert not any("R-006" in r for r in result["rules_applied"])

    def test_r006_violated(self):
        """R-006: 超过 3 个景点（4 个 slot）"""
        plan = {
            "days": [
                {
                    "morning": {"spot_name": "A"},
                    "afternoon": {"spot_name": "B"},
                    "evening": {"spot_name": "C"},
                    "night": {"spot_name": "D"},
                }
            ]
        }
        result = validate_plan(plan)
        assert any("R-006" in r for r in result["rules_applied"])

    def test_r008_high_altitude_for_family(self):
        """R-008: 亲子团避免西岭雪山（Day2，避免 R-001 干扰）"""
        plan = {
            "group_type": "亲子",
            "days": [
                {"morning": {"spot_name": "成都大熊猫繁育研究基地"}, "afternoon": {}},
                {"morning": {"spot_name": "西岭雪山"}, "afternoon": {}},
            ],
        }
        result = validate_plan(plan)
        assert any("R-008" in r for r in result["rules_applied"])

    def test_empty_plan(self):
        assert validate_plan({}) == {"rules_applied": []}
        assert validate_plan({"days": []}).get("days") == []
