import base64
import logging
from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import requests

logger = logging.getLogger(__name__)

def get_photos_service(
    access_token: str,
    refresh_token: str = None,
    client_id: str = None,
    client_secret: str = None,
    token_uri: str = None
):
    """Create Google Photos service with full OAuth credentials."""
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret
    )
    return build(
        'photoslibrary', 'v1',
        credentials=credentials,
        discoveryServiceUrl='https://photoslibrary.googleapis.com/$discovery/rest?version=v1'
    )

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