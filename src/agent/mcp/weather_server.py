"""
Mock 天气查询 MCP Server
通过 FastMCP 暴露天气查询工具，供工作流中的知识库节点调用
"""
import random
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("travel-weather")


MOCK_CITIES = {
    "北京": "Beijing",
    "上海": "Shanghai",
    "广州": "Guangzhou",
    "深圳": "Shenzhen",
    "成都": "Chengdu",
    "杭州": "Hangzhou",
    "三亚": "Sanya",
    "哈尔滨": "Harbin",
    "昆明": "Kunming",
    "重庆": "Chongqing",
}

WEATHER_CONDITIONS = ["晴朗", "多云", "阴天", "小雨", "中雨", "大雨", "雷阵雨", "小雪", "雾霾", "大风"]


@mcp.tool(
    name="query_weather",
    description="查询指定城市的天气预报，支持日期参数",
)
def query_weather(city: str, date: str = "") -> str:
    """
    查询天气信息

    Args:
        city: 城市名称（中文或英文），如"北京"、"上海"
        date: 日期（可选），格式 YYYY-MM-DD，为空则查询当天

    Returns:
        天气信息文本
    """
    city_en = MOCK_CITIES.get(city, city)

    if date:
        try:
            query_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            query_date = datetime.now()
    else:
        query_date = datetime.now()

    condition = random.choice(WEATHER_CONDITIONS)
    temp_high = random.randint(15, 38)
    temp_low = temp_high - random.randint(5, 15)
    humidity = random.randint(40, 90)
    wind_speed = random.randint(1, 8)
    uv_index = random.randint(1, 10)
    visibility = random.choice(["优", "良", "一般", "较差"])

    date_str = query_date.strftime("%Y年%m月%d日")
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[query_date.weekday()]

    tips = []
    if "雨" in condition:
        tips.append("出门请携带雨具")
    if temp_high > 35:
        tips.append("高温天气，注意防暑")
    if temp_low < 5:
        tips.append("气温较低，注意保暖")
    if uv_index > 7:
        tips.append("紫外线强度高，建议涂抹防晒")
    if wind_speed > 5:
        tips.append("风力较大，注意高空坠物")

    result = (
        f"📍 {city} · {date_str}（{weekday}）\n"
        f"☀️ 天气：{condition}\n"
        f"🌡️ 温度：{temp_low}°C ~ {temp_high}°C\n"
        f"💧 湿度：{humidity}%\n"
        f"🌬️ 风速：{wind_speed}级\n"
        f"👁️ 能见度：{visibility}\n"
        f"🔆 紫外线指数：{uv_index}\n"
    )

    if tips:
        result += f"\n💡 温馨提示：{'；'.join(tips)}"

    return result


@mcp.tool(
    name="query_flight_weather_impact",
    description="查询航班天气影响，判断目的地天气是否适合飞行",
)
def query_flight_weather_impact(departure: str, arrival: str, date: str = "") -> str:
    """
    查询航班对应的天气影响

    Args:
        departure: 出发城市
        arrival: 到达城市
        date: 日期（可选）

    Returns:
        航班天气影响评估
    """
    dep_weather = query_weather(departure, date)
    arr_weather = query_weather(arrival, date)

    severe_conditions = ["大雨", "雷阵雨", "大雪", "大风", "雾霾"]
    dep_severe = any(c in dep_weather for c in severe_conditions)
    arr_severe = any(c in arr_weather for c in severe_conditions)

    impact = "正常"
    advice = "当前天气状况良好，航班正常运行。"

    if dep_severe and arr_severe:
        impact = "高风险"
        advice = "出发地和目的地均受恶劣天气影响，建议关注航空公司最新通知，做好延误或取消的准备。"
    elif dep_severe:
        impact = "注意"
        advice = f"出发地{departure}受恶劣天气影响，可能导致起飞延误，建议提前查询航班动态。"
    elif arr_severe:
        impact = "注意"
        advice = f"目的地{arrival}受恶劣天气影响，可能导致降落延误或备降，建议关注航班动态。"

    return (
        f"✈️ 航班天气影响评估\n"
        f"路线：{departure} → {arrival}\n"
        f"影响等级：{impact}\n\n"
        f"—— 出发地信息 ——\n{dep_weather}\n"
        f"—— 目的地信息 ——\n{arr_weather}\n"
        f"💡 建议：{advice}"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
