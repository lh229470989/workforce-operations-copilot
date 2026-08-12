"""ASGI entry point for Streamable HTTP MCP transport."""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .server import mcp


async def health(_: Request) -> JSONResponse:
    """Keep container health checks separate from the MCP protocol endpoint."""

    return JSONResponse({"status": "ok", "protocol": "mcp", "transport": "streamable-http"})


app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
)
app.routes.insert(0, Route("/health", health, methods=["GET"]))
