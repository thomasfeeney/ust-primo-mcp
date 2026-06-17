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
    sort: str = "relevance",
    resource_type: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """Search the University of St. Thomas library catalog.

    Call this whenever a user asks what the UST library has on a topic, or
    wants books/materials they can actually borrow or access through the
    library. Iterate with different queries and fields to explore a topic
    (e.g. search creator names you discover in earlier results).

    Match the user's intent with `sort` and `resource_type`:
      - When they want recent/latest/new material ("most recent articles
        on...", "latest research"), pass sort="newest".
      - When they ask for a specific kind of material, pass resource_type:
        "articles" (also "papers", "studies", "peer-reviewed research",
        "journal articles"), "books", "book_chapters", "journals",
        "dissertations", "reviews", "newspaper_articles", or "audio_video".

    Args:
        query: Search terms (natural keywords work well).
        field: Where to match — "any" (default), "title", "creator", or "subject".
        scope: "ust" (default) searches only UST's own catalog records.
            "ust_plus_articles" also includes the Central Discovery Index of
            articles. You normally don't set this directly — asking for
            resource_type="articles" (or other article-like types) switches to
            the blended index automatically.
        sort: "relevance" (default), "newest", or "oldest" (by publication date).
        resource_type: Restrict to one material type (see list above). Article-
            like types pull from the Central Discovery Index, which is Ex Libris
            proprietary content; use them when the user clearly wants that kind
            of material.
        limit: Results per call, 1-25 (default 10).
        offset: Skip this many results (for paging).

    Returns total counts and records with title, creator, date, availability,
    physical location, and a permalink into the library's discovery interface.
    """
    return await primo.search(
        query,
        field=field,
        scope=scope,
        sort=sort,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )


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
