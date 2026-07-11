"""
MCP 客户端封装层
提供统一的接口供工作流节点调用 MCP 服务器工具
"""
import asyncio
import json
import sys
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MCPClient:
    """
    MCP 客户端封装

    包装 MCP 的 ClientSession，提供同步接口供工作流节点调用
    """

    def __init__(self, server_script: str, server_name: str = "mcp-server"):
        self.server_script = server_script
        self.server_name = server_name

    def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> str:
        """
        同步调用 MCP 工具

        由于 MCP 客户端是异步接口，这里用 asyncio.run 封装为同步调用
        """
        return asyncio.run(self._call_tool_async(tool_name, arguments or {}))

    async def _call_tool_async(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result = await session.call_tool(tool_name, arguments=arguments)

                    if hasattr(result, "content") and result.content:
                        text_parts = [
                            c.text for c in result.content
                            if hasattr(c, "text")
                        ]
                        return "\n".join(text_parts)

                    return str(result)
        except Exception as e:
            logger.error(
                "MCP 工具调用失败",
                server=self.server_name,
                tool=tool_name,
                error=str(e),
            )
            return f""

    def list_tools(self) -> list:
        """列出 MCP 服务器上可用的工具"""
        return asyncio.run(self._list_tools_async())

    async def _list_tools_async(self) -> list:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return [
                        {"name": t.name, "description": t.description}
                        for t in tools.tools
                    ]
        except Exception as e:
            logger.error(
                "MCP 工具列表获取失败",
                server=self.server_name,
                error=str(e),
            )
            return []


# 单例：天气查询 MCP 客户端
_weather_client: Optional[MCPClient] = None


def get_weather_client() -> MCPClient:
    """获取天气查询 MCP 客户端单例"""
    global _weather_client
    if _weather_client is None:
        _weather_client = MCPClient(
            server_script="src/agent/mcp/weather_server.py",
            server_name="travel-weather",
        )
    return _weather_client
