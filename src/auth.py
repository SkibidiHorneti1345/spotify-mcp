import logging
import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError
from . import config

logger = logging.getLogger("spotify_mcp.auth")

# Scope list authorizing all actions required by tools
SPOTIFY_SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-library-read",
    "user-library-modify",
    "user-top-read"
]
SCOPE_STR = " ".join(SPOTIFY_SCOPES)

# Global Spotify/OAuth caches for connection reuse
_spotify_client = None
_oauth_manager = None
_oauth_manager_config = None

def get_oauth_manager():
    """Initializes and returns the SpotifyOAuth manager.
    Returns None if client credentials are not configured.
    """
    global _oauth_manager, _oauth_manager_config

    if not config.CLIENT_ID or not config.CLIENT_SECRET:
        logger.debug("Spotify Client ID or Secret is missing in config.")
        return None

    cache_key = (
        config.CLIENT_ID,
        config.CLIENT_SECRET,
        config.REDIRECT_URI,
        config.CACHE_PATH,
        SCOPE_STR,
    )

    if _oauth_manager is not None and _oauth_manager_config == cache_key:
        return _oauth_manager
    
    try:
        _oauth_manager = SpotifyOAuth(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
            redirect_uri=config.REDIRECT_URI,
            scope=SCOPE_STR,
            cache_path=config.CACHE_PATH,
            open_browser=False  # Non-interactive CLI environment
        )
        _oauth_manager_config = cache_key
        return _oauth_manager
    except SpotifyOauthError as e:
        logger.error(f"Failed to create SpotifyOAuth manager: {e}")
        _oauth_manager = None
        _oauth_manager_config = None
        return None

def is_authenticated() -> bool:
    """Checks if a valid access token exists or can be refreshed from cache."""
    oauth_manager = get_oauth_manager()
    if not oauth_manager:
        return False
    try:
        token_info = oauth_manager.get_cached_token()
        return token_info is not None
    except Exception as e:
        logger.error(f"Error checking cached token: {e}")
        return False

def get_spotify_client() -> spotipy.Spotify:
    """Returns an authenticated spotipy.Spotify client instance.
    Lazily initializes and reuses the client while keeping the token refreshed.
    Raises RuntimeError if credentials or authentication tokens are missing.
    """
    global _spotify_client
    
    oauth_manager = get_oauth_manager()
    if not oauth_manager:
        raise RuntimeError(
            "Spotify Client ID or Secret is not configured. "
            "Please set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in a .env file "
            "under '/root/Spotify MCP/.env'."
        )
    
    # Try retrieving/refreshing token
    token_info = None
    try:
        token_info = oauth_manager.get_cached_token()
    except Exception as e:
        logger.error(f"Failed to retrieve/refresh cached token: {e}")
    
    if not token_info:
        raise RuntimeError(
            "Spotify is not authenticated. "
            "Please retrieve the authentication URL using the `get_auth_url` tool, "
            "log in, and authorize. Then, run the `complete_auth` tool with the redirect URL."
        )
    
    # Lazy creation of the Spotify client using the oauth manager.
    # We do not pass `auth=...` directly because that bypasses auto-refreshing.
    if _spotify_client is None:
        _spotify_client = spotipy.Spotify(
            auth_manager=oauth_manager,
            requests_timeout=10
        )
        
    return _spotify_client

def get_auth_url() -> str:
    """Generates the OAuth URL that the user needs to visit to authorize the server."""
    oauth_manager = get_oauth_manager()
    if not oauth_manager:
        raise RuntimeError(
            "Spotify Client ID or Secret is not configured. "
            "Please set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in your .env file."
        )
    return oauth_manager.get_authorize_url()

def complete_auth(callback_url: str) -> str:
    """Exchanges authorization code from the redirect URL for credentials and caches them."""
    oauth_manager = get_oauth_manager()
    if not oauth_manager:
        raise RuntimeError("Spotify credentials not configured.")
    
    try:
        # Extract code from callback URL and exchange it
        code = oauth_manager.parse_response_code(callback_url)
        # get_access_token exchanges code and automatically writes it to the CACHE_PATH
        token_info = oauth_manager.get_access_token(code, as_dict=True)
        if token_info:
            # Clear cached client to force re-instantiation
            global _spotify_client
            _spotify_client = None
            return "Authentication completed successfully! Tokens cached."
        else:
            return "Failed to complete authentication: OAuth server returned no tokens."
    except Exception as e:
        logger.exception("Error during authentication completion")
        return f"Authentication failed: {str(e)}"
