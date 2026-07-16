from fastmcp import FastMCP
from pathlib import Path
import logging
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("fastmcp").setLevel(logging.WARNING)

mcp = FastMCP("HTTP File Server")

BASE_DIR = Path(__file__).parent / "workspace"
BASE_DIR.mkdir(exist_ok=True)

def is_within_roots(path: Path) -> bool:
    """Check if path is within allowed roots directory."""
    try:
        path.resolve().relative_to(BASE_DIR.resolve())
        return True
    except ValueError:
        return False

@mcp.tool()
def read_file(filepath: str) -> str:
    """Read a file from the workspace directory."""
    path = BASE_DIR / filepath

    if not is_within_roots(path):
        return f"Error: Access denied - path outside workspace roots"

    if not path.exists():
        return f"Error: File not found: {filepath}"

    try:
        content = path.read_text()
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """Write content to a file in the workspace directory."""
    path = BASE_DIR / filepath

    if not is_within_roots(path):
        return f"Error: Access denied - path outside workspace roots"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Successfully wrote {len(content)} characters to {filepath}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

@mcp.tool()
def list_files(directory: str = ".") -> str:
    """List files in a directory within the workspace."""
    path = BASE_DIR / directory

    if not is_within_roots(path):
        return f"Error: Access denied - path outside workspace roots"

    if not path.exists():
        return f"Error: Directory not found: {directory}"

    if not path.is_dir():
        return f"Error: Not a directory: {directory}"

    try:
        files = []
        for item in sorted(path.iterdir()):
            relative_path = item.relative_to(BASE_DIR)
            tyle_type = "DIR" if item.is_dir() else "FILE"
            size = item.stat() if item.is_file() else 0
            files.append(f"{file_type}: {relative_path} ({size} bytes)")

        return "\n".join(files) if files else "Directory is empty"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

@mcp.tool()
def analyze_code(code: str, focus: str = "quality") -> str:
    """Analyze code focusing on specified aspect.

    In a full MCP implementation with bidirectional communication, this tools would send a sampling/createMessage JSON-RPC request to the client. For this educational lab, we return a message indicating where sampling would occur.
    """
    return f"""[SAMPLING TRIGGER]
    This tool would send a sampling/createMessage request to the client:

    {{
        'method': 'sampling/createMessage'
        'params': {{
            'messages': [{{'role': 'user', 'content': {{
                'type': 'text',
                'text': 'Analyze this code for {focus}:\\n{code[:50]}...'
            }}}}],
            'maxTokens': 500
        }}
    }}

    The client would:
    1. Show approval dialog to user
    2. If approved, call LLM with the prompt
    3. Return LLM response to server
    4. Server would use response to complete analysis

    Note: Full bidirectional sampling requires low-level MCP SDK.
    This simplified version demonstrates the concept."""