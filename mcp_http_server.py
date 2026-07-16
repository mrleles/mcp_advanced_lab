from fastmcp import FastMCP
from pathlib import Path
import logging
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("fastmcp").setLevel(logging.WARNING)

mcp = FastMCP("HTTP File Server")