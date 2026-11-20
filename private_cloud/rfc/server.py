"""Entry point of the Private Cloud / On-Premise RFC MCP server."""

import tools  # noqa: F401  Importing the package registers all tools on core.app.mcp.
from core.app import mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
