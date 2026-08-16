"""MCP HTTP Server Module.

This module implements a FastMCP-based HTTP server demonstrating core Model Context Protocol
concepts:
    1. HTTP Transport: Exposes an MCP endpoint over Streamable HTTP for remote connectivity.
    2. Filesystem Roots: Enforces security boundaries ensuring file operations are confined
       strictly within the designated workspace directory.
    3. Tools: Exposes file operations (`read_file`, `write_file`, `list_files`) and an educational
       sampling trigger (`analyze_code`).
    4. Resources: Exposes static workspace file resources via URI templates.
    5. Prompts: Provides reusable prompt engineering templates for code review and security analysis.
    6. Sampling: Demonstrates server-initiated LLM requests (conceptually simulating `sampling/createMessage`).
"""

import logging
from pathlib import Path
import warnings

from fastmcp import FastMCP

# Suppress deprecation warnings and configure FastMCP logger
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("fastmcp").setLevel(logging.WARNING)

# Initialize the FastMCP server instance
mcp = FastMCP("HTTP File Server")

# Define the root workspace directory for bounded file operations
BASE_DIR: Path = Path(__file__).parent / "workspace"
BASE_DIR.mkdir(exist_ok=True)


def is_within_roots(path: Path) -> bool:
    """Validate that a target path resides within the allowed workspace root directory.

    Prevents directory traversal attacks (e.g., `../../etc/passwd`) by resolving the
    canonical absolute path and verifying it starts with `BASE_DIR`.

    Args:
        path: Path object to validate.

    Returns:
        True if the path is safely inside `BASE_DIR`, False otherwise.
    """
    try:
        path.resolve().relative_to(BASE_DIR.resolve())
        return True
    except ValueError:
        return False


# ============================================================================
# MCP Tools
# ============================================================================


@mcp.tool()
def read_file(filepath: str) -> str:
    """Read the contents of a file within the workspace directory.

    Args:
        filepath: Relative path to the file within the workspace.

    Returns:
        The text content of the file, or an error message if access is denied
        or the file is not found.
    """
    path = BASE_DIR / filepath

    if not is_within_roots(path):
        return "Error: Access denied - path outside workspace roots"

    if not path.exists():
        return f"Error: File not found: {filepath}"

    try:
        content = path.read_text(encoding="utf-8")
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """Write text content to a file in the workspace directory.

    Creates parent directories automatically if they do not exist.

    Args:
        filepath: Relative path to the file to create or overwrite.
        content: The text content to write.

    Returns:
        A success message with the written character count, or an error message.
    """
    path = BASE_DIR / filepath

    if not is_within_roots(path):
        return "Error: Access denied - path outside workspace roots"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {filepath}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@mcp.tool()
def list_files(directory: str = ".") -> str:
    """List all files and subdirectories within a workspace directory.

    Args:
        directory: Relative path of the directory to list (defaults to workspace root).

    Returns:
        A newline-delimited list of files and directories with sizes, or an error message.
    """
    path = BASE_DIR / directory

    if not is_within_roots(path):
        return "Error: Access denied - path outside workspace roots"

    if not path.exists():
        return f"Error: Directory not found: {directory}"

    if not path.is_dir():
        return f"Error: Not a directory: {directory}"

    try:
        files = []
        for item in sorted(path.iterdir()):
            relative_path = item.relative_to(BASE_DIR)
            file_type = "DIR" if item.is_dir() else "FILE"
            size = item.stat().st_size if item.is_file() else 0
            files.append(f"{file_type}: {relative_path} ({size} bytes)")

        return "\n".join(files) if files else "Directory is empty"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@mcp.tool()
def analyze_code(code: str, focus: str = "quality") -> str:
    """Analyze source code focusing on a specified aspect using simulated MCP sampling.

    In a complete MCP implementation with bidirectional communication, this tool would
    send a `sampling/createMessage` JSON-RPC request to the client. For this educational
    lab, it returns a structured representation of the sampling payload.

    Args:
        code: The source code snippet to analyze.
        focus: The review focus area (e.g., 'quality', 'security', 'performance').

    Returns:
        A formatted explanation demonstrating how MCP sampling operates.
    """
    return f"""[SAMPLING TRIGGER]
    This tool would send a sampling/createMessage request to the client:

    {{
        'method': 'sampling/createMessage',
        'params': {{
            'messages': [{{'role': 'user', 'content': {{
                'type': 'text',
                'text': 'Analyze this code for {focus}:\\n{code[:50]}...'
            }}}}],
            'maxTokens': 500
        }}
    }}

    The client would:
    1. Show an approval dialog to the user
    2. If approved, call the LLM with the prompt
    3. Return the LLM response to the server
    4. The server would use the response to complete its analysis

    Note: Full bidirectional sampling requires low-level MCP SDK handlers.
    This simplified version demonstrates the core protocol concept."""


# ============================================================================
# MCP Resources
# ============================================================================


@mcp.resource("file://workspace/{filename}")
def get_workspace_file(filename: str) -> str:
    """Read a file from the workspace as an MCP Resource.

    Args:
        filename: Relative name or path of the workspace file.

    Returns:
        The raw text content of the workspace file.

    Raises:
        ValueError: If the file is outside workspace roots or does not exist.
    """
    path = BASE_DIR / filename

    if not is_within_roots(path):
        raise ValueError("Access denied - path outside workspace roots")

    if not path.exists():
        raise ValueError(f"File not found: {filename}")

    return path.read_text(encoding="utf-8")


# ============================================================================
# MCP Prompts
# ============================================================================


@mcp.prompt()
def review_code(filename: str) -> str:
    """Generate a structured prompt template to review code from a workspace file.

    Args:
        filename: Name of the file to be reviewed.

    Returns:
        A rendered prompt string guiding an LLM through a thorough code review.
    """
    return f"""Please review the code in file '{filename}' and provide:
        1. A summary of what the code does
        2. Potential bugs or issues
        3. Suggestions for improvements
        4. Security concerns
        5. Code quality assessment
        Focus on readability, maintainability, and best practices."""


@mcp.prompt()
def analyze_security(filename: str) -> str:
    """Generate a structured prompt template to analyze the security of a workspace file.

    Args:
        filename: Name of the file to analyze.

    Returns:
        A rendered prompt string guiding an LLM through security vulnerability analysis.
    """
    return f"""Perform a security analysis of '{filename}' focusing on:
        1. Input validation and sanitization
        2. Authentication and authorization checks
        3. Potential injection vulnerabilities
        4. Data exposure risks
        5. Error handling security
        Provide specific line numbers and remediation suggestions."""


# ============================================================================
# Server Entrypoint
# ============================================================================

if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 8000
    print(f"Starting HTTP MCP Server on http://{HOST}:{PORT}")
    print(f"Workspace roots: {BASE_DIR}")

    mcp.run(transport="http", host=HOST, port=PORT)
