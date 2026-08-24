import sys
import json
import gradio as gr
from openai import OpenAI
from mcp_http_client_base import MCPHTTPClient

class MCPHTTPHostApp(MCPHTTPClient):
    """AI host application that uses OpenAI LLM with MCP HTTP server tools."""

    def __init__(self, server_url: str, roots_dir: str):
        super().__init__(server_url, roots_dir)
        self.conversation_history = []

        self.llm_client = OpenAI()
        self.model = "gpt-4o-mini"

    async def get_available_tools(self):
        """Get all available tools in OpenAI function calling format."""
        await self.connect()

        mcp_tools = await self.list_tools()

        openai_tools = []

        for tool in mcp_tools:
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"Execute {tool_name}",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }