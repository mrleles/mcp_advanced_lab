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

            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                schema = tool.inputSchema
                if isinstance(schema, dict):
                    if "properties" in schema:
                        tool_schema["function"]["parameters"]["properties"] = schema["properties"]
                    if "required" in schema and schema["required"]:
                        tool_schema["function"]["parameters"]["required"] = schema["required"]

            openai_tools.append(tool_schema)

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": "mcp_list_resources",
                    "description": "List all available resources from the MCP server",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            })

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": "mcp_read_resource",
                    "description": "Read a specific resource by URI from the MCP server",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "uri": {
                                "type": "string",
                                "description": "The URI of the resource to read (for example, 'file://workspace/example.txt')"
                            }
                        },
                        "required": ["uri"]
                    }
                }
            })

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": "mcp_list_prompts",
                    "description": "List all available prompt templates from the MCP server",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            })

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": "mcp_get_prompt",
                    "description": "Get a rendered prompt template from the MCP server",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": " The name of the prompt template"
                            },
                            "arguments": {
                                "type": "object",
                                "description": "Arguments for the prompt template"
                            }
                        },
                        "required": ["name"]
                    }
                }
            })

            return openai_tools

    async def execute_tool(self, tool_name: str, arguments: dict):
        """Execute a tool call (real MCP tool or synthetic helper)."""
        await self.connect()

        if tool_name == "mcp_list_resources":
            resources = await self.list_resources()
            result = "Available resources:\n"
            for resource in resources:
                result += f"- {resource.uriTemplate}"
                if resource.name:
                    result += f" ({resource.name})"
                if resource.description:
                    result += f": {resource.description}"
                result += "\n"
            return result

        if tool_name == "mcp_read_resource":
            uri = arguments.get("uri")
            if not uri:
                return "Error: URI is required"
            try:
                contents = await self.read_resource(uri)
                if isinstance(contents, list) and len(contents) > 0:
                    content = contents[0]
                    if hasattr(content, 'text'):
                        return content.text
                    return str(content)
                return str(contents)
            except Exception as e:
                return f"Error reading resource: {str(e)}"

        if tool_name == "mcp_list_prompts":
            prompts = await self.list_prompts()
            result = "Available prompts:\n"
            for prompt in prompts:
                result += f" - {prompt.name}"
                if prompt.description:
                    result += f": {prompt.description}"
                if hasattr(prompt, 'arguments') and prompt.arguments:
                    args = [arg.name for arg in prompt.arguments]
                    result += f" (args: {', '.join(args)})"
                result += "\n"
            return result

        if tool_name == "mcp_get_prompt":
            name = arguments.get("name")
            prompt_args = arguments.get("arguments", {})
            if not name:
                return "Error: Prompt name is required"
            try:
                messages = await self.get_prompt(name, prompt_args)
                result = f"Prompt: {name}\n\n"
                for msg in messages:
                    role = getattr(msg, 'role', 'unknown')
                    content = getattr(msg, 'content', '')
                    if hasattr(content, 'text'):
                        content = content.text
                    result += f"[{role}]: {content}\n\n"
                return result
            except Exception as e:
                return f"Error getting prompt: {str(e)}"