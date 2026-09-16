"""
高德地图天气查询工具

调用高德开放平台天气接口，获取成都实时天气和未来天气预报。
- 实况天气：https://restapi.amap.com/v3/weather/weatherInfo?extensions=base
- 预报天气：https://restapi.amap.com/v3/weather/weatherInfo?extensions=all
"""
import httpx
from app.config import settings
from app.logger import logger

# 成都城市编码
CHENGDU_ADCODE = "510100"

# 天气现象中文映射（高德返回的是英文/代码，这里做兜底映射）
WEATHER_MAP = {
    "sunny": "晴",
    "cloudy": "多云",
    "overcast": "阴",
    "rain": "雨",
    "snow": "雪",
    "fog": "雾",
    "haze": "霾",
}


def get_weather(city: str = "成都", extensions: str = "all") -> str:
    """
    查询指定城市的天气。

    Args:
        city: 城市名称（默认成都），目前只支持成都
        extensions: "base" 实况天气 | "all" 预报天气（默认 all）

    Returns:
        格式化的天气信息字符串
    """
    if not settings.AMAP_API_KEY:
        return "天气查询暂不可用（未配置高德 API Key）"

    # 目前只支持成都
    adcode = CHENGDU_ADCODE

    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": settings.AMAP_API_KEY,
        "city": adcode,
        "extensions": extensions,
        "output": "JSON",
    }

    try:
        resp = httpx.get(url, params=params, timeout=10)
        data = resp.json()

        if data.get("status") != "1":
            logger.warning(f"高德天气接口返回异常: {data}")
            return f"天气查询失败：{data.get('info', '未知错误')}"

        if extensions == "base":
            # 实况天气
            lives = data.get("lives", [])
            if not lives:
                return "暂无天气数据"
            live = lives[0]
            return (
                f"【成都实时天气】\n"
                f"天气：{live.get('weather', '未知')}\n"
                f"温度：{live.get('temperature', '未知')}°C\n"
                f"风向：{live.get('winddirection', '未知')}风\n"
                f"风力：{live.get('windpower', '未知')}级\n"
                f"湿度：{live.get('humidity', '未知')}%\n"
                f"发布时间：{live.get('reporttime', '未知')}"
            )
        else:
            # 预报天气
            forecasts = data.get("forecasts", [])
            if not forecasts:
                return "暂无天气预报数据"
            forecast = forecasts[0]
            city_name = forecast.get("city", "成都")
            report_time = forecast.get("reporttime", "")
            casts = forecast.get("casts", [])

            lines = [f"【{city_name}未来天气预报】（发布时间：{report_time}）"]
            for cast in casts:
                date = cast.get("date", "")
                week = cast.get("week", "")
                day_weather = cast.get("dayweather", "")
                night_weather = cast.get("nightweather", "")
                day_temp = cast.get("daytemp", "")
                night_temp = cast.get("nighttemp", "")
                day_wind = cast.get("daywind", "")
                day_power = cast.get("daypower", "")
                lines.append(
                    f"{date}（周{week}）：{day_weather}转{night_weather}，"
                    f"{night_temp}~{day_temp}°C，{day_wind}风{day_power}级"
                )
            return "\n".join(lines)

    except Exception as e:
        logger.error(f"高德天气接口调用失败: {e}")
        return f"天气查询失败：{str(e)}"


# 天气相关关键词，用于判断是否需要调用天气接口
WEATHER_KEYWORDS = [
    "天气", "气温", "温度", "下雨", "下雪", "降雨", "降雪",
    "晴天", "阴天", "多云", "刮风", "风力", "湿度",
    "穿什么", "带伞", "防晒", "冷不冷", "热不热",
    "weather", "temperature", "rain", "snow",
]


def is_weather_query(message: str) -> bool:
    """判断用户消息是否涉及天气查询。"""
    msg = message.lower()
    return any(kw in msg for kw in WEATHER_KEYWORDS)
