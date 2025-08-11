import os
import json
import logging
import contextlib
import uvicorn
import click
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
    format_photo_metadata, 
    format_album_metadata,
    get_photo_url_with_size,
    download_photo_as_base64,
    build_search_filters
)

# Configure logging
logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_PHOTOS_MCP_SERVER_PORT = int(os.getenv("GOOGLE_PHOTOS_MCP_SERVER_PORT", "5001"))

# Context variable to store the access token for each request
auth_token_context: ContextVar[str] = ContextVar('auth_token')

# Define enums
class PhotoSize(Enum):
    SMALL = "s"
    MEDIUM = "m"
    LARGE = "l"
    DOWNLOAD = "d"

class MediaType(Enum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"

def get_auth_token() -> str:
    """Get the authentication token from context."""
    try:
        return auth_token_context.get()
    except LookupError:
        raise RuntimeError("Authentication token not found in request context")

def remove_none_values(params: dict) -> dict:
    """Remove None values from parameters dictionary."""
    return {k: v for k, v in params.items() if v is not None}

async def search_photos(
    query: str,
    page_size: int = 25,
    page_token: Optional[str] = None,
    include_location: bool = True
) -> Dict[str, Any]:
    """Search for photos by text query."""
    logger.info(f"Executing tool: search_photos with query: {query}")
    try:
        access_token = get_auth_token()
        service = get_photos_service(access_token)
        
        # Build search request
        request_body = {
            "pageSize": min(page_size, 100),
            "filters": build_search_filters()
        }
        
        if page_token:
            request_body["pageToken"] = page_token
        
        # Execute search
        request = service.mediaItems().search(body=request_body)
        response = request.execute()
        
        # Format photos
        photos = []
        for item in response.get('mediaItems', []):
            formatted_photo = format_photo_metadata(item, include_location)
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
        logger.exception(f"Error executing tool search_photos: {e}")
        raise e

async def search_photos_by_location(
    location_name: str,
    page_size: int = 25,
    page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Search for photos by location name."""
    logger.info(f"Executing tool: search_photos_by_location with location: {location_name}")
    try:
        access_token = get_auth_token()
        service = get_photos_service(access_token)
        
        # Build search request with location filter
        request_body = {
            "pageSize": min(page_size, 100),
            "filters": build_search_filters(location_name=location_name)
        }
        
        if page_token:
            request_body["pageToken"] = page_token
        
        # Execute search
        request = service.mediaItems().search(body=request_body)
        response = request.execute()
        
        # Format photos
        photos = []
        for item in response.get('mediaItems', []):
            # Only include photos that have location data
            if 'mediaMetadata' in item and 'location' in item['mediaMetadata']:
                formatted_photo = format_photo_metadata(item, include_location=True)
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
        logger.exception(f"Error executing tool search_photos_by_location: {e}")
        raise e

async def get_photo(
    photo_id: str,
    include_base64: bool = False,
    include_location: bool = True
) -> Dict[str, Any]:
    """Get detailed information about a specific photo."""
    logger.info(f"Executing tool: get_photo with photo_id: {photo_id}")
    try:
        access_token = get_auth_token()
        service = get_photos_service(access_token)
        
        # Get photo details
        request = service.mediaItems().get(mediaItemId=photo_id)
        response = request.execute()
        
        # Format photo
        photo = format_photo_metadata(response, include_location)
        
        # Add base64 data if requested
        if include_base64:
            photo_url = get_photo_url_with_size(response.get('baseUrl', ''), 'm')
            base64_data = await download_photo_as_base64(photo_url)
            photo['base64Data'] = base64_data
        
        return photo
        
    except HttpError as e:
        logger.error(f"Google Photos API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool get_photo: {e}")
        raise e

async def get_photo_url(
    photo_id: str,
    size: str = "m"
) -> Dict[str, Any]:
    """Get photo URL with specified size."""
    logger.info(f"Executing tool: get_photo_url with photo_id: {photo_id}, size: {size}")
    try:
        access_token = get_auth_token()
        service = get_photos_service(access_token)
        
        # Get photo details
        request = service.mediaItems().get(mediaItemId=photo_id)
        response = request.execute()
        
        base_url = response.get('baseUrl', '')
        photo_url = get_photo_url_with_size(base_url, size)
        
        return {
            "photoUrl": photo_url,
            "baseUrl": base_url,
            "size": size
        }
        
    except HttpError as e:
        logger.error(f"Google Photos API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool get_photo_url: {e}")
        raise e

async def list_albums(
    page_size: int = 20,
    page_token: Optional[str] = None
) -> Dict[str, Any]:
    """List all albums in the user's Google Photos library."""
    logger.info(f"Executing tool: list_albums")
    try:
        access_token = get_auth_token()
        service = get_photos_service(access_token)
        
        # Build request parameters
        params = {"pageSize": min(page_size, 50)}
        if page_token:
            params["pageToken"] = page_token
        
        # Execute request
        request = service.albums().list(**params)
        response = request.execute()
        
        # Format albums
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

async def get_album(album_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific album."""
    logger.info(f"Executing tool: get_album with album_id: {album_id}")
    try:
        access_token = get_auth_token()
        service = get_photos_service(access_token)
        
        # Get album details
        request = service.albums().get(albumId=album_id)
        response = request.execute()
        
        # Format album
        album = format_album_metadata(response)
        
        return album
        
    except HttpError as e:
        logger.error(f"Google Photos API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool get_album: {e}")
        raise e

async def list_album_photos(
    album_id: str,
    page_size: int = 25,
    page_token: Optional[str] = None,
    include_location: bool = True
) -> Dict[str, Any]:
    """List photos in a specific album."""
    logger.info(f"Executing tool: list_album_photos with album_id: {album_id}")
    try:
        access_token = get_auth_token()
        service = get_photos_service(access_token)
        
        # Build search request for album
        request_body = {
            "pageSize": min(page_size, 100),
            "albumId": album_id
        }
        
        if page_token:
            request_body["pageToken"] = page_token
        
        # Execute search
        request = service.mediaItems().search(body=request_body)
        response = request.execute()
        
        # Format photos
        photos = []
        for item in response.get('mediaItems', []):
            formatted_photo = format_photo_metadata(item, include_location)
            photos.append(formatted_photo)
        
        return {
            "albumId": album_id,
            "photos": photos,
            "nextPageToken": response.get('nextPageToken'),
            "totalCount": len(photos)
        }
        
    except HttpError as e:
        logger.error(f"Google Photos API error: {e}")
        error_detail = json.loads(e.content.decode('utf-8'))
        raise RuntimeError(f"Google Photos API Error ({e.resp.status}): {error_detail.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        logger.exception(f"Error executing tool list_album_photos: {e}")
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

    # Create the MCP server instance
    app = Server("google-photos-mcp-server")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="search_photos",
                description="Search for photos by text query in Google Photos",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for photos"
                        },
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
                    },
                    "required": ["query"]
                }
            ),
            types.Tool(
                name="search_photos_by_location",
                description="Search for photos by location name in Google Photos",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "locationName": {
                            "type": "string",
                            "description": "Location name to search for"
                        },
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
                        }
                    },
                    "required": ["locationName"]
                }
            ),
            types.Tool(
                name="get_photo",
                description="Get detailed information about a specific photo",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "photoId": {
                            "type": "string",
                            "description": "ID of the photo to retrieve"
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
                name="get_photo_url",
                description="Get photo URL with specified size",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "photoId": {
                            "type": "string",
                            "description": "ID of the photo"
                        },
                        "size": {
                            "type": "string",
                            "enum": ["s", "m", "l", "d"],
                            "description": "Photo size: s=small(150px), m=medium(400px), l=large(1024px), d=download original",
                            "default": "m"
                        }
                    },
                    "required": ["photoId"]
                }
            ),
            types.Tool(
                name="list_albums",
                description="List all albums in Google Photos",
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
                name="get_album",
                description="Get detailed information about a specific album",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "albumId": {
                            "type": "string",
                            "description": "ID of the album to retrieve"
                        }
                    },
                    "required": ["albumId"]
                }
            ),
            types.Tool(
                name="list_album_photos",
                description="List photos in a specific album",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "albumId": {
                            "type": "string",
                            "description": "ID of the album"
                        },
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
                    },
                    "required": ["albumId"]
                }
            )
        ]

    @app.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        
        if name == "search_photos":
            result = await search_photos(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "search_photos_by_location":
            result = await search_photos_by_location(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_photo":
            result = await get_photo(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_photo_url":
            result = await get_photo_url(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list_albums":
            result = await list_albums(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_album":
            result = await get_album(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list_album_photos":
            result = await list_album_photos(**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            raise ValueError(f"Unknown tool: {name}")

    # Set up SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        logger.info("Handling SSE connection")
        
        # Extract auth token from headers (allow None - will be handled at tool level)
        auth_token = request.headers.get('x-auth-token')
        
        # Set the auth token in context for this request (can be None)
        token = auth_token_context.set(auth_token or "")
        try:
            async for message in sse.handle_post_message(request):
                yield message
        finally:
            auth_token_context.reset(token)
        
        # return Response()

    # Set up StreamableHTTP transport
    session_manager = StreamableHTTPSessionManager(
        app=app,
        event_store=None,  # Stateless mode - can be changed to use an event store
        json_response=json_response,
        stateless=True,
    )

    async def handle_streamable_http(
        scope: Scope, receive: Receive, send: Send
    ) -> None:
        logger.info("Handling StreamableHTTP request")
        
        # Extract auth token from headers (allow None - will be handled at tool level)
        headers = dict(scope.get("headers", []))
        auth_token = headers.get(b'x-auth-token')
        if auth_token:
            auth_token = auth_token.decode('utf-8')
        
        # Set the auth token in context for this request (can be None/empty)
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
            # SSE routes
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
            
            # StreamableHTTP route
            Mount("/mcp", app=handle_streamable_http),
        ],
        lifespan=lifespan,
    )

    logger.info(f"Google Photos MCP Server starting on port {port} with dual transports:")
    logger.info(f"  - SSE endpoint: http://localhost:{port}/sse")
    logger.info(f"  - StreamableHTTP endpoint: http://localhost:{port}/mcp")

    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

    return 0

if __name__ == "__main__":
    main()