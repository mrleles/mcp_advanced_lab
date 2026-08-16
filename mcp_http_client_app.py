"""MCP HTTP Client GUI Application.

This module provides a graphical user interface (GUI) built with Gradio to interact
with a remote Model Context Protocol (MCP) server over HTTP.

Features:
    - Tool Exploration & Execution: Discover server tools and execute them with JSON arguments.
    - Resource Inspection: Browse available resource templates and fetch file/resource contents.
    - Prompt Templates: Inspect server prompt definitions, input arguments, and preview rendered prompts.
"""

import json
import sys
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from mcp_http_client_base import MCPHTTPClient


class MCPHTTPClientApp(MCPHTTPClient):
    """GUI client application extending the base HTTP client with a Gradio interface.

    Attributes:
        tools_cache: Cached list of tool tuples `(name, formatted_label)`.
        prompts_cache: Cached list of prompt objects retrieved from the server.
    """

    def __init__(self, server_url: str, roots_dir: str) -> None:
        """Initialize the MCP HTTP GUI client.

        Args:
            server_url: The base URL of the remote MCP HTTP server.
            roots_dir: The allowed local workspace directory path.
        """
        super().__init__(server_url, roots_dir)
        self.tools_cache: List[Tuple[str, str]] = []
        self.prompts_cache: List[Any] = []

    async def gui_list_tools(self) -> Tuple[str, Any]:
        """Fetch and format the list of tools for display in the GUI.

        Returns:
            A tuple containing:
                - Formatted markdown/text list of tools and descriptions.
                - Gradio dropdown update with tool names as choices.
        """
        try:
            await self.connect()
            tools = await self.list_tools()
            self.tools_cache = [(t.name, f"{t.name}: {t.description}") for t in tools]
            output = "\n".join([f"- **{t.name}**: {t.description or 'No description'}" for t in tools])
            choices = [t.name for t in tools]
            return output if output else "No tools available", gr.update(choices=choices)
        except Exception as e:
            return f"Error listing tools: {str(e)}", gr.update(choices=[])

    async def gui_call_tool(self, tool_name: Optional[str], arguments_json: str) -> str:
        """Call a selected tool with JSON arguments from the GUI.

        Args:
            tool_name: The name of the tool selected in the dropdown.
            arguments_json: Raw JSON string representing tool arguments.

        Returns:
            The text output returned from the tool execution or an error message.
        """
        await self.connect()
        if not tool_name:
            return "Error: Please select a tool from the dropdown first."

        try:
            args: Dict[str, Any] = json.loads(arguments_json) if arguments_json.strip() else {}
        except json.JSONDecodeError as err:
            return f"Error: Invalid JSON format in arguments: {err}"

        try:
            result = await self.call_tool(tool_name, args)
            output_parts = []
            if hasattr(result, "content") and result.content:
                for content in result.content:
                    if hasattr(content, "text"):
                        output_parts.append(content.text)
                    else:
                        output_parts.append(str(content))
            return "\n".join(output_parts) if output_parts else "Tool executed with no output."
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"

    async def gui_list_resources(self) -> str:
        """Fetch and format the list of resource templates from the MCP server.

        Returns:
            A formatted string of all available resource templates and URIs.
        """
        try:
            await self.connect()
            resources = await self.list_resources()
            if not resources:
                return "No resources available on server."

            output = []
            for r in resources:
                name = getattr(r, "name", None) or getattr(r, "description", "Unnamed resource")
                uri_template = getattr(r, "uriTemplate", None) or getattr(r, "uri", "N/A")
                output.append(f"- **{name}**\n  URI Template: `{uri_template}`")

            return "\n\n".join(output)
        except Exception as e:
            return f"Error listing resources: {str(e)}"

    async def gui_read_resource(self, uri: str) -> str:
        """Read and display the contents of a resource specified by URI.

        Args:
            uri: The URI of the resource to read (e.g. 'file://workspace/README.md').

        Returns:
            The resource content string or an error message.
        """
        await self.connect()
        if not uri or not uri.strip():
            return "Error: Please enter a resource URI."

        try:
            result = await self.read_resource(uri.strip())
            output_parts = []
            if hasattr(result, "contents") and result.contents:
                for content in result.contents:
                    if hasattr(content, "text"):
                        output_parts.append(content.text)
                    else:
                        output_parts.append(str(content))
            return "\n".join(output_parts) if output_parts else "Resource is empty."
        except Exception as e:
            return f"Error reading resource '{uri}': {str(e)}"

    async def gui_list_prompts(self) -> Tuple[str, Any]:
        """Fetch and format all prompt templates available on the MCP server.

        Returns:
            A tuple containing:
                - Formatted list of prompt templates with argument requirements.
                - Gradio dropdown update with prompt names.
        """
        try:
            await self.connect()
            prompts = await self.list_prompts()
            self.prompts_cache = prompts
            output = []
            choices = []
            for p in prompts:
                args_info = ""
                if hasattr(p, "arguments") and p.arguments:
                    arg_names = [arg.name for arg in p.arguments]
                    args_info = f" (arguments: {', '.join(arg_names)})"
                output.append(f"- **{p.name}**: {p.description or 'No description'}{args_info}")
                choices.append(p.name)

            formatted_output = "\n".join(output) if output else "No prompts available on server."
            return formatted_output, gr.update(choices=choices)
        except Exception as e:
            return f"Error listing prompts: {str(e)}", gr.update(choices=[])

    async def gui_get_prompt(self, prompt_name: Optional[str], arguments_json: str) -> str:
        """Render a selected prompt template with provided arguments.

        Args:
            prompt_name: The name of the prompt template selected from the dropdown.
            arguments_json: Raw JSON string of argument key-value pairs.

        Returns:
            The rendered prompt messages formatted for review.
        """
        await self.connect()
        if not prompt_name:
            return "Error: Please select a prompt from the dropdown first."

        try:
            args: Dict[str, Any] = json.loads(arguments_json) if arguments_json.strip() else {}
        except json.JSONDecodeError as err:
            return f"Error: Invalid JSON format in arguments: {err}"

        try:
            result = await self.get_prompt(prompt_name, args)
            description = getattr(result, "description", prompt_name)
            output_parts = [f"### Rendered Prompt: {description}\n"]

            if hasattr(result, "messages") and result.messages:
                for msg in result.messages:
                    role = getattr(msg, "role", "message").upper()
                    content = msg.content
                    if hasattr(content, "text"):
                        content_text = content.text
                    elif isinstance(content, dict):
                        content_text = content.get("text", str(content))
                    else:
                        content_text = str(content)
                    output_parts.append(f"**[{role}]**\n{content_text}\n")

            return "\n".join(output_parts)
        except Exception as e:
            return f"Error rendering prompt '{prompt_name}': {str(e)}"

    def create_interface(self) -> gr.Blocks:
        """Construct the Gradio UI tabbed layout and bind interactive event handlers.

        Returns:
            gr.Blocks: The initialized Gradio application interface.
        """
        with gr.Blocks(title="MCP HTTP Client") as interface:
            gr.Markdown("# MCP HTTP Client - Remote Server Access")
            gr.Markdown(
                f"**Connected Server:** `{self.server_url}`  \n"
                f"**Workspace Roots:** `{self.roots_dir}`  \n"
                "Interact with remote MCP server tools, resources, and prompt templates."
            )

            with gr.Tabs():
                # ------------------------------------------------------------
                # Tab 1: Tools Management
                # ------------------------------------------------------------
                with gr.Tab("Tools"):
                    gr.Markdown("### Discover and Execute Server Tools")
                    with gr.Row():
                        with gr.Column(scale=1):
                            list_tools_btn = gr.Button("List Tools", variant="primary")
                            tools_output = gr.Markdown(value="Click 'List Tools' to discover tools.")

                        with gr.Column(scale=1):
                            tool_dropdown = gr.Dropdown(label="Select Tool", choices=[], interactive=True)
                            tool_args = gr.Textbox(
                                label="Arguments (JSON)",
                                placeholder='{"filepath": "example.txt"}',
                                lines=3,
                            )
                            call_tool_btn = gr.Button("Call Tool", variant="primary")
                            tool_result = gr.Textbox(label="Tool Execution Result", lines=8)

                    list_tools_btn.click(
                        fn=self.gui_list_tools,
                        outputs=[tools_output, tool_dropdown],
                    )
                    call_tool_btn.click(
                        fn=self.gui_call_tool,
                        inputs=[tool_dropdown, tool_args],
                        outputs=tool_result,
                    )

                # ------------------------------------------------------------
                # Tab 2: Resources Management
                # ------------------------------------------------------------
                with gr.Tab("Resources"):
                    gr.Markdown("### Access Server Resources")
                    with gr.Row():
                        with gr.Column(scale=1):
                            list_resources_btn = gr.Button("List Resource Templates", variant="primary")
                            resources_output = gr.Markdown(value="Click 'List Resource Templates' to discover resources.")

                        with gr.Column(scale=1):
                            resource_uri = gr.Textbox(
                                label="Resource URI",
                                placeholder="file://workspace/README.md",
                                lines=1,
                            )
                            read_resource_btn = gr.Button("Read Resource", variant="primary")
                            resource_content = gr.Textbox(label="Resource Content", lines=10)

                    list_resources_btn.click(
                        fn=self.gui_list_resources,
                        outputs=resources_output,
                    )
                    read_resource_btn.click(
                        fn=self.gui_read_resource,
                        inputs=resource_uri,
                        outputs=resource_content,
                    )

                # ------------------------------------------------------------
                # Tab 3: Prompts Management
                # ------------------------------------------------------------
                with gr.Tab("Prompts"):
                    gr.Markdown("### List and Render Prompt Templates")
                    with gr.Row():
                        with gr.Column(scale=1):
                            list_prompts_btn = gr.Button("List Prompts", variant="primary")
                            prompts_output = gr.Markdown(value="Click 'List Prompts' to discover prompt templates.")

                        with gr.Column(scale=1):
                            prompt_dropdown = gr.Dropdown(label="Select Prompt", choices=[], interactive=True)
                            prompt_args = gr.Textbox(
                                label="Arguments (JSON)",
                                placeholder='{"filename": "mcp_http_server.py"}',
                                lines=2,
                            )
                            get_prompt_btn = gr.Button("Get Rendered Prompt", variant="primary")
                            prompt_result = gr.Textbox(label="Prompt Messages", lines=10)

                    list_prompts_btn.click(
                        fn=self.gui_list_prompts,
                        outputs=[prompts_output, prompt_dropdown],
                    )
                    get_prompt_btn.click(
                        fn=self.gui_get_prompt,
                        inputs=[prompt_dropdown, prompt_args],
                        outputs=prompt_result,
                    )

        return interface


def main() -> None:
    """Parse CLI arguments and start the Gradio GUI client server."""
    if len(sys.argv) < 3:
        print("Usage: python mcp_http_client_app.py <server_url> <roots_dir>")
        print("Example: python mcp_http_client_app.py http://127.0.0.1:8000 /path/to/workspace")
        sys.exit(1)

    server_url = sys.argv[1]
    roots_dir = sys.argv[2]

    client = MCPHTTPClientApp(server_url, roots_dir)
    interface = client.create_interface()
    interface.queue().launch(server_name="127.0.0.1", server_port=7861)


if __name__ == "__main__":
    main()