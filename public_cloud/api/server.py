"""Public Cloud standard SAP read APIs, using this provider's tenant and communication user."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.mm_api import create_server

mcp = create_server(Path(__file__).resolve().parent, public=True)

if __name__ == "__main__":
    mcp.run(transport="stdio")
