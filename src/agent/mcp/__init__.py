"""
MCP 工具模块
提供 MCP 服务器和客户端封装，供工作流节点调用外部工具
"""
from src.agent.mcp.client import MCPClient, get_weather_client
from src.agent.mcp.weather_server import mcp

__all__ = [
    "MCPClient",
    "get_weather_client",
    "mcp",
]
