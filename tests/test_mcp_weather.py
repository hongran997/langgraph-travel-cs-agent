"""
MCP 天气查询集成测试
验证 Mock MCP 服务器和知识库节点的天气查询集成
"""
import pytest
from src.agent.mcp.client import get_weather_client
from src.agent.nodes.knowledge_base import _is_weather_query, _extract_city


class TestMCPWeatherServer:
    """测试 Mock 天气 MCP 服务器"""

    def test_query_weather_with_city(self):
        """测试通过 MCP 查询城市天气"""
        client = get_weather_client()
        result = client.call_tool("query_weather", {"city": "北京"})

        assert result is not None
        assert "北京" in result
        assert "°C" in result
        assert "天气" in result or "温度" in result

    def test_query_weather_with_date(self):
        """测试带日期的天气查询"""
        client = get_weather_client()
        result = client.call_tool("query_weather", {"city": "上海", "date": "2026-07-15"})

        assert result is not None
        assert "上海" in result
        assert "2026年07月15日" in result

    def test_query_flight_weather_impact(self):
        """测试航班天气影响查询"""
        client = get_weather_client()
        result = client.call_tool(
            "query_flight_weather_impact",
            {"departure": "北京", "arrival": "上海"},
        )

        assert result is not None
        assert "北京" in result
        assert "上海" in result
        assert "影响等级" in result

    def test_list_tools(self):
        """测试列出 MCP 服务器工具列表"""
        client = get_weather_client()
        tools = client.list_tools()

        assert len(tools) >= 2
        tool_names = [t["name"] for t in tools]
        assert "query_weather" in tool_names
        assert "query_flight_weather_impact" in tool_names


class TestWeatherQueryDetection:
    """测试天气查询检测逻辑"""

    def test_detect_weather_keywords(self):
        """测试天气关键词检测"""
        assert _is_weather_query("北京天气怎么样") is True
        assert _is_weather_query("明天上海会下雨吗") is True
        assert _is_weather_query("What's the weather in Tokyo") is True
        assert _is_weather_query("我要退票") is False
        assert _is_weather_query("帮我查一下订单") is False

    def test_extract_city_from_phrase(self):
        """测试从消息中提取城市"""
        assert _extract_city("北京的天气怎么样") == "北京"
        assert _extract_city("上海天气如何") == "上海"
        assert _extract_city("去三亚天气怎么样") == "三亚"
        assert _extract_city("帮我查一下订单") is None
        assert _extract_city("天气怎么样") is None
