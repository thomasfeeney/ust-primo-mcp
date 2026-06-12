"""ASGI app: landing page + demo search API + the MCP endpoint.

One Cloud Run service serves all three, so anyone who receives the MCP
URL also finds the explanation of what it is and the decisions it raises:

    /            human-readable landing page (what, why, how, key decisions)
    /api/search  demo endpoint used by the landing page's live search box
    /mcp         the Model Context Protocol endpoint for Claude
"""

import contextlib
import pathlib

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import primo
from server import mcp

BASE_DIR = pathlib.Path(__file__).parent


async def index(request: Request) -> FileResponse:
    return FileResponse(BASE_DIR / "templates" / "index.html")


async def api_search(request: Request) -> JSONResponse:
    query = request.query_params.get("q", "").strip()
    if not query:
        return JSONResponse({"error": "missing q parameter"}, status_code=400)
    scope = request.query_params.get("scope", "ust")
    try:
        result = await primo.search(query, scope=scope, limit=8)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse({"error": "catalog request failed"}, status_code=502)
    return JSONResponse(result)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        yield


# mcp.streamable_http_app() serves the protocol at /mcp within the mount.
app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/search", api_search),
        Route("/healthz", health),
        Mount("/static", app=StaticFiles(directory=BASE_DIR / "static")),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
