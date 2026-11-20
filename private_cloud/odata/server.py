"""Private Cloud standard SAP read APIs, configured independently from RFC."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.mm_api import create_server

mcp = create_server(Path(__file__).resolve().parent, public=False)

if __name__ == "__main__":
    mcp.run(transport="stdio")
