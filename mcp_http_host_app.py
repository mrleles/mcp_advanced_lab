import sys
import json
import gradio as gr
from openai import OpenAI
from mcp_http_client_base import MCPHTTPClient

class MCPHTTPHostApp(MCPHTTPClient):
    """AI host application that uses OpenAI LLM with MCP HTTP server tools"""

    def __init__(self, server_url: str, roots_dir: str):
        super().__init__(server_url, roots_dir)
        self.conversation_history = []

        self.llm_client = OpenAI()
        self.model = "gpt-4o-mini"