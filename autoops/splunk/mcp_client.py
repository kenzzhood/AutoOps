"""Splunk MCP Server integration for read/query operations."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx

from autoops.models.config import AutoOpsConfig
from autoops.utils.logger import get_logger

logger = get_logger(__name__)


class SplunkMCPClient:
    """Client for official Splunk MCP server at /services/mcp."""

    def __init__(self, config: AutoOpsConfig | None = None):
        self.config = config or AutoOpsConfig.from_env()
        self.endpoint = self.config.mcp_endpoint
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        token = self.config.splunk_token or self.config.splunk_password
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _jsonrpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(verify=False, timeout=8.0) as client:
            resp = await client.post(
                self.endpoint,
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                raise ConnectionError(
                    f"Splunk MCP unavailable at {self.endpoint} (HTTP {resp.status_code}). "
                    "Install Splunk MCP Server app (Splunkbase 7931) and set SPLUNK_MCP_URL."
                )
            text = resp.text.strip()
            if text.startswith("event:"):
                for line in text.splitlines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if "result" in data:
                            return data["result"]
                        if "error" in data:
                            raise RuntimeError(data["error"])
            data = resp.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data.get("result")

    async def initialize(self) -> dict[str, Any]:
        return await self._jsonrpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "autoops", "version": "0.1.0"},
            },
        )

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._jsonrpc("tools/list")
        if isinstance(result, dict):
            return result.get("tools", [])
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._jsonrpc("tools/call", {"name": name, "arguments": arguments})
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if content and isinstance(content, list):
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    try:
                        return json.loads(first["text"])
                    except json.JSONDecodeError:
                        return first["text"]
        return result

    async def run_search(
        self,
        query: str,
        earliest: str = "-30m",
        latest: str = "now",
    ) -> list[dict[str, Any]]:
        """Execute SPL search via MCP tool or fallback REST."""
        if os.getenv("AUTOOPS_SKIP_MCP", "").lower() in ("1", "true", "yes"):
            return await self._rest_search_fallback(query, earliest, latest)
        try:
            tools = await self.list_tools()
            tool_names = [t.get("name", "") for t in tools]
            search_tool = next(
                (n for n in tool_names if "search" in n.lower()),
                None,
            )
            if search_tool:
                result = await self.call_tool(
                    search_tool,
                    {"query": query, "earliest_time": earliest, "latest_time": latest},
                )
                if isinstance(result, list):
                    return result
                if isinstance(result, dict):
                    return result.get("results", result.get("rows", [result]))
                return [{"raw": str(result)}]
        except Exception as exc:
            logger.warning("MCP search failed, using REST fallback: %s", exc)

        return await self._rest_search_fallback(query, earliest, latest)

    async def _rest_search_fallback(
        self,
        query: str,
        earliest: str,
        latest: str,
    ) -> list[dict[str, Any]]:
        """Fallback to Splunk REST oneshot when MCP unavailable."""
        import asyncio

        from autoops.splunk.rest_client import SplunkRESTClient

        rest = SplunkRESTClient(self.config)

        def _run() -> list[dict[str, Any]]:
            return rest.run_search(query, earliest, latest)

        return await asyncio.to_thread(_run)

    async def test_connection(self) -> bool:
        try:
            await self.initialize()
            return True
        except Exception as exc:
            logger.error("MCP connection test failed: %s", exc)
            return False

    @asynccontextmanager
    async def session(self):
        await self.initialize()
        yield self
