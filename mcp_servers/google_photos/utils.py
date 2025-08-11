# NOTE: As of April 2025, this integration uses the Picker API for user photo selection
# and Library API only for app-created content.
# See: https://developers.google.com/photos/library/guides/api-changes

import os
import base64
import aiohttp
import logging
from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import requests

logger = logging.getLogger(__name__)

def get_photos_service(
    access_token: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    token_uri: str
):
    """
    Returns a Google Photos Library API service client.
    Only app-created content is accessible due to Google Photos API changes (March 2025).
    """
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=token_uri,
        scopes=[
            "https://www.googleapis.com/auth/photoslibrary.appendonly",
            "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
        ]
    )
    return build("photoslibrary", "v1", credentials=credentials)

def get_picker_service(
    access_token: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    token_uri: str
) -> Any:
    """
    Returns a Google Photos Picker API service client with full OAuth credentials
    (so we can refresh the token when it expires).
    """
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=token_uri,
        scopes=["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"],
    )
    return build(
        "photospicker",
        "v1",
        credentials=credentials,
        discoveryServiceUrl="https://photospicker.googleapis.com/$discovery/rest?version=v1",
    )

def format_picker_media_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format a picked media item from the Picker API."""
    media_file = item.get('mediaFile', {})
    metadata = media_file.get('mediaFileMetadata', {})
    
    formatted_item = {
        'id': item.get('id'),
        'createTime': item.get('createTime'),
        'type': item.get('type'),
        'filename': media_file.get('filename'),
        'mimeType': media_file.get('mimeType'),
        'baseUrl': media_file.get('baseUrl'),
        'width': metadata.get('width'),
        'height': metadata.get('height'),
        'cameraMake': metadata.get('cameraMake'),
        'cameraModel': metadata.get('cameraModel')
    }
    
    # Add type-specific metadata
    if 'photoMetadata' in metadata:
        photo_meta = metadata['photoMetadata']
        formatted_item['photoMetadata'] = {
            'focalLength': photo_meta.get('focalLength'),
            'apertureFNumber': photo_meta.get('apertureFNumber'),
            'isoEquivalent': photo_meta.get('isoEquivalent'),
            'exposureTime': photo_meta.get('exposureTime')
        }
    elif 'videoMetadata' in metadata:
        video_meta = metadata['videoMetadata']
        formatted_item['videoMetadata'] = {
            'fps': video_meta.get('fps'),
            'processingStatus': video_meta.get('processingStatus')
        }
    
    return formatted_item

def format_photo_metadata(photo: Dict[str, Any], include_location: bool = True) -> Dict[str, Any]:
    """Format photo metadata for response."""
    formatted = {
        'id': photo.get('id'),
        'filename': photo.get('filename'),
        'description': photo.get('description', ''),
        'productUrl': photo.get('productUrl'),
        'baseUrl': photo.get('baseUrl'),
        'mimeType': photo.get('mimeType'),
        'mediaMetadata': {}
    }
    
    # Add media metadata
    if 'mediaMetadata' in photo:
        media = photo['mediaMetadata']
        formatted['mediaMetadata'] = {
            'creationTime': media.get('creationTime'),
            'width': media.get('width'),
            'height': media.get('height')
        }
        
        # Add photo-specific metadata
        if 'photo' in media:
            photo_meta = media['photo']
            formatted['mediaMetadata']['photo'] = {
                'cameraMake': photo_meta.get('cameraMake'),
                'cameraModel': photo_meta.get('cameraModel'),
                'focalLength': photo_meta.get('focalLength'),
                'apertureFNumber': photo_meta.get('apertureFNumber'),
                'isoEquivalent': photo_meta.get('isoEquivalent'),
                'exposureTime': photo_meta.get('exposureTime')
            }
        
        # Add video-specific metadata
        if 'video' in media:
            video_meta = media['video']
            formatted['mediaMetadata']['video'] = {
                'fps': video_meta.get('fps'),
                'status': video_meta.get('status')
            }
    
    # Add location data if requested and available
    if include_location and 'mediaMetadata' in photo:
        location = photo['mediaMetadata'].get('location')
        if location:
            formatted['location'] = {
                'locationName': location.get('locationName'),
                'latlng': location.get('latlng')
            }
    
    return formatted

def format_album_metadata(album: Dict[str, Any]) -> Dict[str, Any]:
    """Format album metadata for response."""
    return {
        'id': album.get('id'),
        'title': album.get('title'),
        'productUrl': album.get('productUrl'),
        'mediaItemsCount': album.get('mediaItemsCount'),
        'coverPhotoBaseUrl': album.get('coverPhotoBaseUrl'),
        'coverPhotoMediaItemId': album.get('coverPhotoMediaItemId'),
        'isWriteable': album.get('isWriteable', False),
        'shareInfo': album.get('shareInfo', {})
    }

def get_photo_url_with_size(base_url: str, size: str) -> str:
    """Generate photo URL with specific size parameter."""
    size_params = {
        's': '=s150',      # Small
        'm': '=s400',      # Medium  
        'l': '=s1024',     # Large
        'd': '=d'          # Download original
    }
    
    param = size_params.get(size, '=s400')
    return f"{base_url}{param}"

async def download_photo_as_base64(photo_url: str) -> str:
    """Download photo and convert to base64."""
    try:
        response = requests.get(photo_url)
        response.raise_for_status()
        return base64.b64encode(response.content).decode('utf-8')
    except Exception as e:
        logger.error(f"Error downloading photo: {e}")
        raise RuntimeError(f"Failed to download photo: {str(e)}")

def build_search_filters(
    location_name: str = None,
    content_categories: List[str] = None,
    media_types: List[str] = None,
    include_archived: bool = False
) -> Dict[str, Any]:
    """Build search filters for Google Photos API."""
    filters = {}
    
    if location_name:
        filters['contentFilter'] = {
            'excludedContentCategories': []
        }
        # Note: Location search requires more complex handling
    
    if content_categories:
        if 'contentFilter' not in filters:
            filters['contentFilter'] = {}
        filters['contentFilter']['includedContentCategories'] = content_categories
    
    if media_types:
        filters['mediaTypeFilter'] = {
            'mediaTypes': media_types
        }
    
    if include_archived:
        filters['includeArchivedMedia'] = True
    
    return filters