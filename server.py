"""MCP server exposing the UST library catalog to AI assistants.

Built with the official MCP Python SDK (FastMCP). Runs stateless over
streamable HTTP so it can be added to Claude as a custom connector and
deployed on Cloud Run with no session affinity.
"""

import primo
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "UST Library Search",
    instructions=(
        "Search the University of St. Thomas (Minnesota) library catalog "
        "(Alma/Primo VE via CLIC/MnPALS). Use search_catalog to find books and "
        "other materials; use get_record for full detail on one result. "
        "Always cite results with their title and permalink so users can reach "
        "the item in the library's own interface."
    ),
    stateless_http=True,
    json_response=True,
    # DNS-rebinding protection rejects any Host other than localhost; it guards
    # local dev servers, not a public HTTPS service whose hostname Cloud Run owns.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def search_catalog(
    query: str,
    field: str = "any",
    scope: str = "ust",
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """Search the University of St. Thomas library catalog.

    Call this whenever a user asks what the UST library has on a topic, or
    wants books/materials they can actually borrow or access through the
    library. Iterate with different queries and fields to explore a topic
    (e.g. search creator names you discover in earlier results).

    Args:
        query: Search terms (natural keywords work well).
        field: Where to match — "any" (default), "title", "creator", or "subject".
        scope: "ust" (default) searches only UST's own catalog records.
            "ust_plus_articles" also includes the Central Discovery Index of
            articles — use only if the user explicitly wants articles, as that
            index is Ex Libris proprietary content pending license review.
        limit: Results per call, 1-25 (default 10).
        offset: Skip this many results (for paging).

    Returns total counts and records with title, creator, date, availability,
    physical location, and a permalink into the library's discovery interface.
    """
    return await primo.search(query, field=field, scope=scope, limit=limit, offset=offset)


@mcp.tool()
async def get_record(record_id: str) -> dict:
    """Fetch full details for one catalog record by its ID.

    Use after search_catalog when the user wants more about a specific item:
    subjects, contributors, description, edition, series, ISBN.

    Args:
        record_id: The "id" value from a search_catalog result
            (e.g. "alma991015373058903691").
    """
    return await primo.get_record(record_id)
