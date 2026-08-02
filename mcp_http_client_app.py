from random import choice
import sys
import json
import gradio as gr
from mcp_http_client_base import MCPHTTPClient

class MCPHTTPClientApp(MCPHTTPClient):
    """GUI client application that extends the base HTTP client with Gradio interface."""

    def __init__(self, server_url: str, roots_dir: str):
        super().__init__(server_url, roots_dir)
        self.tools_cache = []
        self.prompts_cache = []

    async def gui_list_tools(self):
        """List tools for GUI."""
        await self.connect()
        tools = await self.list_tools()
        self.tools_cache = [(t.name f"{t.name}: {t.description}") for t in tools]
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

async def gui_list_resources(self):
    """List resources for GUI."""
    await self.connect()
    resources = await self.list_resources()
    if resources:
        output = []
        for r in resources:
            name getattr(r, 'name', getattr(r, 'descripion', 'Unnamed resource'))
            uri_template = getattr(r, 'uriTemplate', getattr(r, 'uri', 'N/A'))
            output.append(f"- {name}\n URI template: {uri_template}")
        return "\n\n".join(output)
    return "No resurces available"

async def gui_read_resource(self, uri):
    """Read a resource from GUI."""
    await self.connect()
    if not uri:
        return "Error: Please enter a resource URI"
    try:
        result = await self.read_resource(uri)
        output = ""
        for content in result.contents:
            if hasattr(content, 'text'):
                output += content.text + "\n"
        return output if output else "No content"
    except Exception as e:
        return f"Error: {e}"

async def gui_list_prompts(self):
    """List prompts for GUI."""
    await self.connect()
    prompts = await self.list_prompts()
    self.prompts_cache = prompts
    output = []
    choices = []
    for p in prompts:
        args_info = ""
        if p.arguments:
            arg_names = [arg.name for arg in p.arguments]
            args_info = f" (args: {', '.join(arg_names)})"
        output.append(f"- {p.name}: {p.description}{args_info}")
        choices.append(p.name)
    return "\n".join(output), gr.update(choices=choice)

async def gui_get_prompt(self, prompt_name, arguments_json):
    """Get a prompt from GUI."""
    if not prompt_name:
        return "Error: Please select a prompt from the dropdown first"
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        result = await self.get_prompt(prompt_name, args)
        output = f"--- Prompt: {result.description} ---\n\n"
        for msg in result.messages:
            content_text = msg.content.text if hasattr(msg.content, 'text') else msg.content.get('text', '')
            output += f"{msg.role}: {content_text}\n"
        return output
    except json.JSONDecodeError:
        return "Error: Invalid JSON format"
    except Exception as e:
        return f"Error: {e}"

def create_interface(self):
    """Create the Gradio interface."""

    with gr.Blocks(title="MCP")