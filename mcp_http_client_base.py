"""Base MCP HTTP Client Module.

This module provides the core client functionality for interacting with Model Context
Protocol (MCP) servers using Streamable HTTP transport. It handles connection lifecycle,
session initialization via an asynchronous exit stack, and exposes asynchronous methods
for discovering and invoking MCP primitives (tools, resources, and prompts).

Architecture:
    - Transport: Streamable HTTP (via `mcp.client.streamable_http.streamablehttp_client`)
    - Session: `mcp.ClientSession` managing JSON-RPC 2.0 communication
    - Lifecycle: `contextlib.AsyncExitStack` ensuring clean teardown of connections
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Suppress verbose internal MCP debug/info logs
logging.getLogger("mcp").setLevel(logging.WARNING)


class MCPHTTPClient:
    """Base MCP HTTP client with pure protocol logic and no GUI dependencies.

    Manages asynchronous connections to an HTTP-based MCP server and provides
    standard methods to interact with server tools, resources, and prompt templates.

    Attributes:
        server_url: Base URL of the remote MCP HTTP server (e.g., 'http://127.0.0.1:8000').
        roots_dir: Filesystem path representing the client workspace boundary.
        session: Active MCP ClientSession instance once connected, or None.
        exit_stack: Asynchronous exit stack for managing context manager lifecycles.
        _connected: Internal boolean flag indicating if the client is connected.
    """

    def __init__(self, server_url: str, roots_dir: str) -> None:
        """Initialize the MCP HTTP Client.

        Args:
            server_url: The base HTTP URL of the MCP server (without trailing `/mcp`).
            roots_dir: The local workspace directory allowed for file operations.
        """
        self.server_url: str = server_url.rstrip("/")
        self.roots_dir: str = roots_dir
        self.session: Optional[ClientSession] = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self._connected: bool = False

    async def connect(self) -> None:
        """Connect to the HTTP MCP server via Streamable HTTP.

        Establishes the SSE/Streamable HTTP connection to `{server_url}/mcp`,
        initializes the client session, and performs protocol handshaking.
        Safe to call multiple times (idempotent if already connected).

        Raises:
            Exception: If connection or session initialization fails.
        """
        if self._connected and self.session is not None:
            return

        mcp_url = f"{self.server_url}/mcp"
        read, write, _ = await self.exit_stack.enter_async_context(
            streamablehttp_client(mcp_url)
        )

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        await self.session.initialize()
        self._connected = True

    async def list_tools(self) -> List[Any]:
        """List all available tools exposed by the MCP server.

        Returns:
            List of Tool objects containing tool names, descriptions, and input schemas.

        Raises:
            RuntimeError: If called before establishing a connection.
        """
        if not self.session:
            raise RuntimeError("Client is not connected. Call connect() first.")
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a tool on the MCP server.

        Args:
            tool_name: The name of the tool to execute.
            arguments: Dictionary of arguments matching the tool's input schema.

        Returns:
            CallToolResult containing content blocks (text/images) returned by the tool.

        Raises:
            RuntimeError: If called before establishing a connection.
        """
        if not self.session:
            raise RuntimeError("Client is not connected. Call connect() first.")
        result = await self.session.call_tool(tool_name, arguments or {})
        return result

    async def list_resources(self) -> List[Any]:
        """List all available resource templates from the MCP server.

        Returns:
            List of ResourceTemplate objects containing URI templates and descriptions.

        Raises:
            RuntimeError: If called before establishing a connection.
        """
        if not self.session:
            raise RuntimeError("Client is not connected. Call connect() first.")
        result = await self.session.list_resource_templates()
        return result.resourceTemplates

    async def read_resource(self, uri: str) -> Any:
        """Read a resource by URI from the MCP server.

        Args:
            uri: The URI of the resource to read (e.g., 'file://workspace/README.md').

        Returns:
            ReadResourceResult containing the contents of the requested resource.

        Raises:
            RuntimeError: If called before establishing a connection.
        """
        if not self.session:
            raise RuntimeError("Client is not connected. Call connect() first.")
        result = await self.session.read_resource(uri)
        return result

    async def list_prompts(self) -> List[Any]:
        """List all available prompt templates from the MCP server.

        Returns:
            List of Prompt objects containing prompt names, descriptions, and arguments.

        Raises:
            RuntimeError: If called before establishing a connection.
        """
        if not self.session:
            raise RuntimeError("Client is not connected. Call connect() first.")
        result = await self.session.list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Get a rendered prompt template from the MCP server.

        Args:
            prompt_name: The name of the prompt template.
            arguments: Dictionary of argument values to populate the template.

        Returns:
            GetPromptResult containing the rendered messages for the prompt.

        Raises:
            RuntimeError: If called before establishing a connection.
        """
        if not self.session:
            raise RuntimeError("Client is not connected. Call connect() first.")
        result = await self.session.get_prompt(prompt_name, arguments or {})
        return result

    async def cleanup(self) -> None:
        """Clean up resources and close the HTTP connection.

        Closes the active session and unwinds all contexts in the exit stack.
        """
        self._connected = False
        self.session = None
        await self.exit_stack.aclose()
