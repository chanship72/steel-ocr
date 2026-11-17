import json

from mcp.types import CallToolResult, TextContent
from mcp.server.fastmcp import FastMCP

from qa import lookup
from table_216 import evaluate

server = FastMCP("steel-ocr")


@server.tool()
def lookup_tensile_strength(grade: str, thickness_mm: str) -> CallToolResult:
    """Get effective tensile strength for a demo grade at a nominal thickness.

    Pass thickness_mm as a positive decimal string in mm (for example "60.1").
    Ask for grade and thickness if missing. Use ontology bounds only when its
    status is ok. The ocr_only fields are the unadjusted table comparison.
    """
    answer = lookup(grade, thickness_mm)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(answer, ensure_ascii=False))],
        structuredContent=answer,
    )



@server.tool()
def lookup_kr_table_216(
    grade: str, metric: str, thickness_mm: str, killed: bool | None = None,
    impact: bool | None = None, carbon_pct: str | None = None, manganese_pct: str | None = None,
) -> CallToolResult:
    """Run live Z3 rules for KR Table 2.1.6.

    Metrics: mn_min or a_plate_carbon_mn (A-grade plate only).
    For B-grade Mn queries, ask for killed and impact conditions if missing.
    Pass decimal measurements as strings. Return answer and applied footnote numbers.
    """
    answer = evaluate(grade, metric, thickness_mm, killed, impact, carbon_pct, manganese_pct)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(answer, ensure_ascii=False))],
        structuredContent=answer,
    )


if __name__ == "__main__":
    server.run(transport="stdio")
