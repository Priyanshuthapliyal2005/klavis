import os
import json
import logging
import contextlib
import uvicorn
import click
import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional
from contextvars import ContextVar
from enum import Enum

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils import (
    get_photos_service,
    get_picker_service,
    format_picker_media_item
)

# Configure logging
logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_PHOTOS_MCP_SERVER_PORT = int(os.getenv("GOOGLE_PHOTOS_MCP_SERVER_PORT", "5001"))

# Load OAuth credentials from environment
GOOGLE_TOKEN_URI = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Context variable to store the access token for each request
auth_token_context: ContextVar[str] = ContextVar('auth_token')

# Define enums
class SessionStatus(Enum):
    PICKING = "PICKING"
    READY = "READY"
    CANCELLED = "CANCELLED"

def get_auth_token() -> str:
    """Get the authentication token from context."""
    try:
        return auth_token_context.get()
    except LookupError:
        raise RuntimeError("Authentication token not found in request context")

def get_photos_service_with_full_credentials(access_token: str):
    """Create Google Photos service with full OAuth credentials."""
    if not all([GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET]):
        missing = []
        if not GOOGLE_REFRESH_TOKEN:
            missing.append("GOOGLE_REFRESH_TOKEN")
        if not GOOGLE_CLIENT_ID:
            missing.append("GOOGLE_CLIENT_ID")
        if not GOOGLE_CLIENT_SECRET:
            missing.append("GOOGLE_CLIENT_SECRET")
        raise RuntimeError(f"Missing required OAuth credentials: {', '.join(missing)}")
    
    return get_photos_service(
        access_token=access_token,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        token_uri=GOOGLE_TOKEN_URI
    )

def get_picker_service_with_credentials(access_token: str):
    """Create Google Photos Picker service with credentials."""
    return get_picker_service(
        access_token,
        os.getenv("GOOGLE_REFRESH_TOKEN"),
        os.getenv("GOOGLE_CLIENT_ID"),
        os.getenv("GOOGLE_CLIENT_SECRET"),
        os.getenv("GOOGLE_TOKEN_URI"),
    )

# PICKER API METHODS

async def google_photos_create_picker_session() -> Dict[str, Any]:
    """Create a new picker session for user photo selection."""
    logger.info("Executing tool: google_photos_create_picker_session")
    try:
        access_token = get_auth_token()
        service = get_picker_service_with_credentials(access_token)
        
        # Create a new picker session
        request = service.sessions().create()
        response = request.execute()
        
        return {
            "sessionId": response.get('id'),
            "pickerUri": response.get('pickerUri'),
            "status": response.get('status')
        }
    except HttpError as e:
        logger.error(f"Google Photos Picker API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos Picker API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool google_photos_create_picker_session: {e}")
        raise e

async def google_photos_get_picker_session(sessionId: str) -> Dict[str, Any]:
    """Get the status of a picker session."""
    logger.info(f"Executing tool: google_photos_get_picker_session with session_id: {sessionId}")
    try:
        access_token = get_auth_token()
        service = get_picker_service_with_credentials(access_token)
        
        request = service.sessions().get(sessionId=sessionId)
        response = request.execute()
        
        return {
            "sessionId": response.get('id'),
            "status": response.get('status'),
            "mediaItemsSet": response.get('mediaItemsSet', False)
        }
    except HttpError as e:
        logger.error(f"Google Photos Picker API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos Picker API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool google_photos_get_picker_session: {e}")
        raise e

async def google_photos_list_picked_media_items(
    sessionId: str,
    pageSize: int = 50,
    pageToken: Optional[str] = None
) -> Dict[str, Any]:
    """List media items picked by the user in a session."""
    logger.info(f"Executing tool: google_photos_list_picked_media_items with session_id: {sessionId}")
    try:
        access_token = get_auth_token()
        service = get_picker_service_with_credentials(access_token)
        
        params = {
            "sessionId": sessionId,
            "pageSize": min(pageSize, 100)
        }
        if pageToken:
            params["pageToken"] = pageToken
        
        request = service.mediaItems().list(**params)
        response = request.execute()
        
        # Format picked media items
        media_items = []
        for item in response.get('mediaItems', []):
            formatted_item = format_picker_media_item(item)
            media_items.append(formatted_item)
        
        return {
            "sessionId": sessionId,
            "mediaItems": media_items,
            "nextPageToken": response.get('nextPageToken'),
            "totalCount": len(media_items)
        }
    except HttpError as e:
        logger.error(f"Google Photos Picker API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos Picker API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool google_photos_list_picked_media_items: {e}")
        raise e

async def google_photos_delete_picker_session(sessionId: str) -> Dict[str, Any]:
    """Delete a picker session."""
    logger.info(f"Executing tool: google_photos_delete_picker_session with session_id: {sessionId}")
    try:
        access_token = get_auth_token()
        service = get_picker_service_with_credentials(access_token)
        
        request = service.sessions().delete(sessionId=sessionId)
        request.execute()
        
        return {"message": f"Session {sessionId} deleted successfully"}
    except HttpError as e:
        logger.error(f"Google Photos Picker API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos Picker API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool google_photos_delete_picker_session: {e}")
        raise e

@click.command()
@click.option("--port", default=GOOGLE_PHOTOS_MCP_SERVER_PORT, help="Port to listen on for HTTP")
@click.option(
    "--log-level",
    default="INFO",
    help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option(
    "--json-response",
    is_flag=True,
    default=False,
    help="Enable JSON responses for StreamableHTTP instead of SSE streams",
)
def main(
    port: int,
    log_level: str,
    json_response: bool,
) -> int:
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Validate required OAuth credentials at startup
    if not all([GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET]):
        missing = []
        if not GOOGLE_REFRESH_TOKEN:
            missing.append("GOOGLE_REFRESH_TOKEN")
        if not GOOGLE_CLIENT_ID:
            missing.append("GOOGLE_CLIENT_ID")
        if not GOOGLE_CLIENT_SECRET:
            missing.append("GOOGLE_CLIENT_SECRET")
        
        logger.error(f"Missing required OAuth credentials: {', '.join(missing)}")
        logger.error("Please set the following environment variables or add them to your .env file:")
        for var in missing:
            logger.error(f"  {var}")
        return 1

    # Create the MCP server instance
    app = Server("google-photos-mcp-server")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            # Picker API tools
            types.Tool(
                name="google_photos_create_picker_session",
                description="Create a new picker session for user photo selection from Google Photos",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.Tool(
                name="google_photos_get_picker_session",
                description="Get the status of a picker session",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sessionId": {
                            "type": "string",
                            "description": "ID of the picker session"
                        }
                    },
                    "required": ["sessionId"]
                }
            ),
            types.Tool(
                name="google_photos_list_picked_media_items",
                description="List media items picked by the user in a session",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sessionId": {
                            "type": "string",
                            "description": "ID of the picker session"
                        },
                        "pageSize": {
                            "type": "integer",
                            "description": "Number of items to return (max 100)",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 50
                        },
                        "pageToken": {
                            "type": "string",
                            "description": "Token for pagination"
                        }
                    },
                    "required": ["sessionId"]
                }
            ),
            types.Tool(
                name="google_photos_delete_picker_session",
                description="Delete a picker session",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sessionId": {
                            "type": "string",
                            "description": "ID of the picker session to delete"
                        }
                    },
                    "required": ["sessionId"]
                }
            )
        ]

    @app.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:

        token = auth_token_context.set(arguments.get("access_token", ""))
        try:
            if name == "google_photos_create_picker_session":
                result = await google_photos_create_picker_session()
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "google_photos_get_picker_session":
                result = await google_photos_get_picker_session(**arguments)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "google_photos_list_picked_media_items":
                result = await google_photos_list_picked_media_items(**arguments)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "google_photos_delete_picker_session":
                result = await google_photos_delete_picker_session(**arguments)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                raise ValueError(f"Unknown tool: {name}")
                
        finally:
            auth_token_context.reset(token)

    # Set up SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        logger.info("Handling SSE connection")

        auth_token = request.headers.get('x-auth-token')
        token = auth_token_context.set(auth_token or "")
        try:
            async for message in sse.handle_post_message(request):
                yield message
        finally:
            auth_token_context.reset(token)

    # Set up StreamableHTTP transport
    session_manager = StreamableHTTPSessionManager(
        app=app,
        event_store=None,
        json_response=json_response,
        stateless=True,
    )

    async def handle_streamable_http(
        scope: Scope, receive: Receive, send: Send
    ) -> None:
        logger.info("Handling StreamableHTTP request")

        headers = dict(scope.get("headers", []))
        auth_token = headers.get(b'x-auth-token')
        if auth_token:
            auth_token = auth_token.decode('utf-8')

        token = auth_token_context.set(auth_token or "")
        try:
            await session_manager.handle_request(scope, receive, send)
        finally:
            auth_token_context.reset(token)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    # Create an ASGI application with routes for both transports
    starlette_app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
            Mount("/mcp", app=handle_streamable_http),
        ],
        lifespan=lifespan,
    )

    logger.info(f"Google Photos MCP Server starting on port {port}")
    logger.info(f"  - SSE endpoint: http://localhost:{port}/sse")
    logger.info(f"  - StreamableHTTP endpoint: http://localhost:{port}/mcp")
    logger.info("  - Uses Picker API for user photo selection")
    logger.info("  - Library API limited to app-created content")

    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

    return 0

if __name__ == "__main__":
    main()