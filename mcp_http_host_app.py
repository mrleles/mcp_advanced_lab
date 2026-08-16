"""AI Host Application with MCP HTTP Server Integration.

This module implements an AI-powered agent host that connects to a remote MCP HTTP server.
It maps MCP tools, resources, and prompts dynamically into OpenAI Function Calling format,
allowing an LLM (e.g., GPT-4o-mini) to autonomously inspect resources, render prompts,
and execute server-side tools (like workspace file operations).

Architecture:
    - Base Client: Inherits from `MCPHTTPClient` for Streamable HTTP transport.
    - LLM Provider: OpenAI API (function calling / tool calling loop).
    - Tool Dispatcher: Automatically bridges LLM tool requests to MCP remote endpoints.
    - UI Layer: Gradio chat interface for conversational interaction with the agent.
"""

import json
import sys
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from mcp_http_client_base import MCPHTTPClient
from openai import OpenAI


class MCPHTTPHostApp(MCPHTTPClient):
    """AI Host application that integrates an OpenAI LLM with remote MCP HTTP server capabilities.

    Attributes:
        conversation_history: In-memory list of chat messages for the OpenAI context.
        llm_client: OpenAI API client instance.
        model: Target OpenAI model identifier (default: 'gpt-4o-mini').
    """

    def __init__(self, server_url: str, roots_dir: str, model: str = "gpt-4o-mini") -> None:
        """Initialize the AI MCP Host Application.

        Args:
            server_url: Base URL of the remote MCP server (e.g., 'http://127.0.0.1:8000').
            roots_dir: Allowed local workspace directory path.
            model: OpenAI model name to use for reasoning and tool calling.
        """
        super().__init__(server_url, roots_dir)
        self.conversation_history: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are an expert AI assistant with access to remote MCP tools, resources, "
                    "and prompt templates. Use the available tools to inspect workspace files, "
                    "read resources, and perform code operations when requested by the user."
                ),
            }
        ]
        self.llm_client: OpenAI = OpenAI()
        self.model: str = model

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Retrieve all server tools and helper actions formatted for OpenAI Function Calling.

        Returns:
            List of dictionary schemas compatible with OpenAI's `tools` parameter.
        """
        await self.connect()

        openai_tools: List[Dict[str, Any]] = []

        # 1. Fetch real MCP tools from the server and convert their JSON schemas
        try:
            mcp_tools = await self.list_tools()
            for tool in mcp_tools:
                tool_schema: Dict[str, Any] = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or f"Execute {tool.name}",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                }

                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    schema = tool.inputSchema
                    if isinstance(schema, dict):
                        if "properties" in schema:
                            tool_schema["function"]["parameters"]["properties"] = schema["properties"]
                        if "required" in schema and schema["required"]:
                            tool_schema["function"]["parameters"]["required"] = schema["required"]

                openai_tools.append(tool_schema)
        except Exception as e:
            print(f"[Warning] Failed to fetch MCP tools: {e}")

        # 2. Add synthetic helper tools for MCP Resources
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "mcp_list_resources",
                "description": "List all available resources and templates from the MCP server.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        })

        openai_tools.append({
            "type": "function",
            "function": {
                "name": "mcp_read_resource",
                "description": "Read a specific resource by URI from the MCP server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "The URI of the resource to read (e.g. 'file://workspace/README.md')",
                        }
                    },
                    "required": ["uri"],
                },
            },
        })

        # 3. Add synthetic helper tools for MCP Prompts
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "mcp_list_prompts",
                "description": "List all available prompt templates from the MCP server.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        })

        openai_tools.append({
            "type": "function",
            "function": {
                "name": "mcp_get_prompt",
                "description": "Get a rendered prompt template from the MCP server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the prompt template to render.",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Key-value argument dictionary for the prompt template.",
                        },
                    },
                    "required": ["name"],
                },
            },
        })

        return openai_tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool call (either an actual MCP server tool or a synthetic helper).

        Args:
            tool_name: The name of the function/tool to execute.
            arguments: Dictionary of arguments passed by the LLM.

        Returns:
            A string containing the result or error message of the execution.
        """
        await self.connect()

        # Handle Resource Helper: List Resources
        if tool_name == "mcp_list_resources":
            try:
                resources = await self.list_resources()
                if not resources:
                    return "No resources available."
                result = "Available resources:\n"
                for resource in resources:
                    uri_tpl = getattr(resource, "uriTemplate", None) or getattr(resource, "uri", "N/A")
                    name = getattr(resource, "name", "")
                    desc = getattr(resource, "description", "")
                    result += f"- {uri_tpl}"
                    if name:
                        result += f" ({name})"
                    if desc:
                        result += f": {desc}"
                    result += "\n"
                return result
            except Exception as e:
                return f"Error listing resources: {str(e)}"

        # Handle Resource Helper: Read Resource
        if tool_name == "mcp_read_resource":
            uri = arguments.get("uri")
            if not uri:
                return "Error: Resource 'uri' parameter is required."
            try:
                contents = await self.read_resource(uri)
                if hasattr(contents, "contents") and contents.contents:
                    parts = [c.text if hasattr(c, "text") else str(c) for c in contents.contents]
                    return "\n".join(parts)
                return str(contents)
            except Exception as e:
                return f"Error reading resource '{uri}': {str(e)}"

        # Handle Prompt Helper: List Prompts
        if tool_name == "mcp_list_prompts":
            try:
                prompts = await self.list_prompts()
                if not prompts:
                    return "No prompt templates available."
                result = "Available prompt templates:\n"
                for p in prompts:
                    args_str = ""
                    if hasattr(p, "arguments") and p.arguments:
                        args_str = f" (args: {', '.join(a.name for a in p.arguments)})"
                    result += f"- {p.name}: {p.description or 'No description'}{args_str}\n"
                return result
            except Exception as e:
                return f"Error listing prompts: {str(e)}"

        # Handle Prompt Helper: Get Prompt
        if tool_name == "mcp_get_prompt":
            prompt_name = arguments.get("name")
            prompt_args = arguments.get("arguments") or {}
            if not prompt_name:
                return "Error: Prompt 'name' parameter is required."
            try:
                result = await self.get_prompt(prompt_name, prompt_args)
                rendered = f"Prompt Template '{prompt_name}':\n"
                if hasattr(result, "messages") and result.messages:
                    for msg in result.messages:
                        role = getattr(msg, "role", "user")
                        content = msg.content.text if hasattr(msg.content, "text") else str(msg.content)
                        rendered += f"[{role}]: {content}\n"
                return rendered
            except Exception as e:
                return f"Error rendering prompt '{prompt_name}': {str(e)}"

        # Handle Standard MCP Tools (e.g. read_file, write_file, list_files, analyze_code)
        try:
            tool_res = await self.call_tool(tool_name, arguments)
            output_parts = []
            if hasattr(tool_res, "content") and tool_res.content:
                for item in tool_res.content:
                    if hasattr(item, "text"):
                        output_parts.append(item.text)
                    else:
                        output_parts.append(str(item))
            return "\n".join(output_parts) if output_parts else "Tool executed successfully (empty response)."
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"

    async def chat(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]],
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Process a user message through the OpenAI agent loop with MCP tool calling.

        Args:
            user_message: The prompt/message sent by the user.
            chat_history: The Gradio chatbot message history list of dicts.

        Returns:
            A tuple of (empty string to clear textbox, updated chat history).
        """
        if not user_message.strip():
            return "", chat_history

        # Append user message to UI chat history and internal conversation memory
        chat_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "user", "content": user_message})

        try:
            tools = await self.get_available_tools()

            # First LLM call: Determine if tools need to be called
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # If the model requested tool calls, execute them and feed results back
            if tool_calls:
                # Add assistant message containing the tool calls to conversation history
                self.conversation_history.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        function_args = {}

                    # Execute the tool
                    tool_output = await self.execute_tool(function_name, function_args)

                    # Add tool response message to conversation history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": tool_output,
                    })

                # Second LLM call: Provide tool outputs to generate the final response
                second_response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=self.conversation_history,
                )
                final_text = second_response.choices[0].message.content or ""
            else:
                final_text = response_message.content or ""

            # Append assistant response to history
            self.conversation_history.append({"role": "assistant", "content": final_text})
            chat_history.append({"role": "assistant", "content": final_text})

        except Exception as e:
            error_msg = f"Error during AI processing: {str(e)}"
            chat_history.append({"role": "assistant", "content": error_msg})

        return "", chat_history

    def clear_history(self) -> Tuple[List[Dict[str, str]], str]:
        """Reset conversation memory and clear chat history.

        Returns:
            Tuple of empty chat history and empty text box value.
        """
        self.conversation_history = [
            {
                "role": "system",
                "content": (
                    "You are an expert AI assistant with access to remote MCP tools, resources, "
                    "and prompt templates. Use the available tools to inspect workspace files, "
                    "read resources, and perform code operations when requested by the user."
                ),
            }
        ]
        return [], ""

    def create_interface(self) -> gr.Blocks:
        """Create the Gradio Chatbot interface for conversational tool execution.

        Returns:
            gr.Blocks: The initialized Gradio application.
        """
        with gr.Blocks(title="AI MCP Host Application") as interface:
            gr.Markdown("# AI MCP Host Application")
            gr.Markdown(
                f"**Remote Server:** `{self.server_url}`  \n"
                f"**Roots Directory:** `{self.roots_dir}`  \n"
                f"**LLM Model:** `{self.model}`  \n\n"
                "Ask questions, inspect workspace files, run security analysis, and execute MCP tools."
            )

            chatbot = gr.Chatbot(
                label="Conversation with MCP Agent",
                type="messages",
                height=500,
            )

            with gr.Row():
                msg_input = gr.Textbox(
                    label="User Prompt",
                    placeholder="e.g., 'List all files in workspace and analyze security of mcp_http_server.py'",
                    lines=2,
                    scale=4,
                )
                submit_btn = gr.Button("Send", variant="primary", scale=1)

            with gr.Row():
                clear_btn = gr.Button("Clear Chat History", variant="secondary")

            # Event Handlers
            submit_btn.click(
                fn=self.chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot],
            )
            msg_input.submit(
                fn=self.chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot],
            )
            clear_btn.click(
                fn=self.clear_history,
                outputs=[chatbot, msg_input],
            )

        return interface


def main() -> None:
    """Parse CLI arguments and launch the AI Host Application."""
    if len(sys.argv) < 3:
        print("Usage: python mcp_http_host_app.py <server_url> <roots_dir> [model]")
        print("Example: python mcp_http_host_app.py http://127.0.0.1:8000 /path/to/workspace gpt-4o-mini")
        sys.exit(1)

    server_url = sys.argv[1]
    roots_dir = sys.argv[2]
    model = sys.argv[3] if len(sys.argv) > 3 else "gpt-4o-mini"

    app = MCPHTTPHostApp(server_url, roots_dir, model=model)
    interface = app.create_interface()
    interface.queue().launch(server_name="127.0.0.1", server_port=7862)


if __name__ == "__main__":
    main()
