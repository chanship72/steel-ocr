"""Run a real MCP stdio tool call without an LLM or API credentials."""
import argparse
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from layout import ROOT


async def main(grade, thickness):
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "mcp_server.py")],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool(
                "lookup_tensile_strength", {"grade": grade, "thickness_mm": thickness}
            )
            if result.isError:
                raise RuntimeError(result.content)
            if result.structuredContent is None:
                raise RuntimeError("Expected a structured tool response")
            print(json.dumps(result.structuredContent, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("grade", nargs="?", default="DEMO-355")
    parser.add_argument("thickness_mm", nargs="?", default="65")
    args = parser.parse_args()
    asyncio.run(main(args.grade, args.thickness_mm))
