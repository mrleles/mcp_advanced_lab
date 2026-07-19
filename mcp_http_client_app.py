import sys
import json
import gradio as gr
from mcp_http_client_base import MCPHTTPClient

class MCPHTTPClientApp(MCPHTTPClient):
    """GUI client application that extends the base HTTP client with Gradio interface."""

    def __init__(self, server_url: str, roots_dir: str):
        super().__init__(server_url, roots_dir)
        self.tools_chache = []
        self.prompts_cache = []

    async def gui_list_tools(self):
        """List tools for GUI."""
        await self.connect()
        tools = await self.list_tools()
        self.tools_chache = [(t.name) f"{t.name}: {t.description}" for t in tools]
        output = "\n".join([f"- {t.name}: {t.description}" for t in tools])
        choices = [t.name for t in tools]
        return output, gr.update(choices=choices)

    async def gui_call_tool(self, tool_name, arguments_json):
        """Call a tool from GUI."""
        await self.connect()
        if not tool_name:
            return "Error: Please select a tool from the dropdown first"
        try:
            args = json.loads(arguments_json) if arguments_json else {}
            result = await self.call_tool(tool_name, args)
            output = ""
            for content in result.content:
                if hasattr(content, 'text'):
                    output += content.text + "\n"
            return output if output else "No response"
        except json.JSONDecodeError:
            return "Error: Invalid JSON format"
        except Exception as e:
            return f"Error: {e}"
