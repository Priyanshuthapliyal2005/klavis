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
    format_photo_metadata,
    format_album_metadata,
    format_picker_media_item,
    get_photo_url_with_size,
    download_photo_as_base64
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
class PhotoSize(Enum):
    SMALL = "s"
    MEDIUM = "m" 
    LARGE = "l"
    DOWNLOAD = "d"

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

async def create_picker_session() -> Dict[str, Any]:
    """Create a new picker session for user photo selection."""
    logger.info("Executing tool: create_picker_session")
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
        logger.exception(f"Error executing tool create_picker_session: {e}")
        raise e

async def get_picker_session(sessionId: str) -> Dict[str, Any]:
    """Get the status of a picker session."""
    logger.info(f"Executing tool: get_picker_session with session_id: {sessionId}")
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
        logger.exception(f"Error executing tool get_picker_session: {e}")
        raise e

async def list_picked_media_items(
    sessionId: str,
    pageSize: int = 50,
    pageToken: Optional[str] = None
) -> Dict[str, Any]:
    """List media items picked by the user in a session."""
    logger.info(f"Executing tool: list_picked_media_items with session_id: {sessionId}")
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
        logger.exception(f"Error executing tool list_picked_media_items: {e}")
        raise e

async def delete_picker_session(sessionId: str) -> Dict[str, Any]:
    """Delete a picker session."""
    logger.info(f"Executing tool: delete_picker_session with session_id: {sessionId}")
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
        logger.exception(f"Error executing tool delete_picker_session: {e}")
        raise e

# EXISTING LIBRARY API METHODS (App-created content only)

async def get_photo(
    photoId: str,
    includeBase64: bool = False,
    includeLocation: bool = True
) -> Dict[str, Any]:
    """Get detailed information about an app-created photo."""
    logger.info(f"Executing tool: get_photo with photo_id: {photoId}")
    access_token = get_auth_token()
    service = get_photos_service_with_full_credentials(access_token)
    
    try:
        request = service.mediaItems().get(mediaItemId=photoId)
        response = request.execute()

        photo = format_photo_metadata(response, includeLocation)

        if includeBase64:
            photo_url = get_photo_url_with_size(response.get('baseUrl', ''), 'm')
            base64_data = await download_photo_as_base64(photo_url)
            photo['base64Data'] = base64_data

        return photo

    except HttpError as e:
        if e.resp.status == 403:
            raise RuntimeError(f"Access denied. Photo {photoId} was not created by this app.")
        logger.error(f"Google Photos API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool get_photo: {e}")
        raise e

async def list_albums(
    pageSize: int = 20,
    pageToken: Optional[str] = None
) -> Dict[str, Any]:
    """List albums created by this app."""
    logger.info("Executing tool: list_albums")
    try:
        access_token = get_auth_token()
        service = get_photos_service_with_full_credentials(access_token)

        params = {"pageSize": min(pageSize, 50)}
        if pageToken:
            params["pageToken"] = pageToken

        request = service.albums().list(**params)
        response = request.execute()

        albums = []
        for album in response.get('albums', []):
            formatted_album = format_album_metadata(album)
            albums.append(formatted_album)

        return {
            "albums": albums,
            "nextPageToken": response.get('nextPageToken'),
            "totalCount": len(albums)
        }

    except HttpError as e:
        logger.error(f"Google Photos API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool list_albums: {e}")
        raise e

async def list_app_created_photos(
    pageSize: int = 25,
    pageToken: Optional[str] = None,
    includeLocation: bool = True
) -> Dict[str, Any]:
    """List photos created by this app."""
    logger.info("Executing tool: list_app_created_photos")
    try:
        access_token = get_auth_token()
        service = get_photos_service_with_full_credentials(access_token)

        params = {"pageSize": min(pageSize, 100)}
        if pageToken:
            params["pageToken"] = pageToken

        request = service.mediaItems().list(**params)
        response = request.execute()

        photos = []
        for item in response.get('mediaItems', []):
            formatted_photo = format_photo_metadata(item, includeLocation)
            photos.append(formatted_photo)

        return {
            "photos": photos,
            "nextPageToken": response.get('nextPageToken'),
            "totalCount": len(photos)
        }

    except HttpError as e:
        logger.error(f"Google Photos API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool list_app_created_photos: {e}")
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
                name="create_picker_session",
                description="Create a new picker session for user photo selection from Google Photos",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.Tool(
                name="get_picker_session",
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
                name="list_picked_media_items",
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
                name="delete_picker_session",
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
            ),
            # Library API tools (app-created content only)
            types.Tool(
                name="get_photo",
                description="Get detailed information about an app-created photo",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "photoId": {
                            "type": "string",
                            "description": "ID of the app-created photo to retrieve"
                        },
                        "includeBase64": {
                            "type": "boolean",
                            "description": "Include base64 encoded image data",
                            "default": False
                        },
                        "includeLocation": {
                            "type": "boolean",
                            "description": "Include location metadata",
                            "default": True
                        }
                    },
                    "required": ["photoId"]
                }
            ),
            types.Tool(
                name="list_albums",
                description="List albums created by this app",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pageSize": {
                            "type": "integer",
                            "description": "Number of albums to return (max 50)",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 20
                        },
                        "pageToken": {
                            "type": "string",
                            "description": "Token for pagination"
                        }
                    }
                }
            ),
            types.Tool(
                name="list_app_created_photos",
                description="List photos created by this app",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pageSize": {
                            "type": "integer",
                            "description": "Number of photos to return (max 100)",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 25
                        },
                        "pageToken": {
                            "type": "string",
                            "description": "Token for pagination"
                        },
                        "includeLocation": {
                            "type": "boolean",
                            "description": "Include location metadata in results",
                            "default": True
                        }
                    }
                }
            )
        ]

    @app.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:

        if name == "create_picker_session":
            result = await create_picker_session()
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_picker_session":
            result = await get_picker_session(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_picked_media_items":
            result = await list_picked_media_items(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "delete_picker_session":
            result = await delete_picker_session(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_photo":
            result = await get_photo(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_albums":
            result = await list_albums(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_app_created_photos":
            result = await list_app_created_photos(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")

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