import logging
import sys
from mcp.server.fastmcp import FastMCP
from . import auth
from . import utils

# Logger configuration (logs go to stderr to prevent stdio corruption)
logger = logging.getLogger("spotify_mcp.server")

from mcp.server.transport_security import TransportSecuritySettings

# Initialize FastMCP Server
# Disable DNS rebinding protection to allow connection from remote MCP clients (e.g. Cursor, Claude Desktop)
security_settings = TransportSecuritySettings(enable_dns_rebinding_protection=False)
mcp = FastMCP("Spotify", transport_security=security_settings)

# =====================================================================
# HELPER FUNCTIONS (Name to URI/ID Resolution)
# =====================================================================

def _resolve_tracks(sp, track_list: list[str]) -> list[str]:
    """Resolves track names to URIs, leaving valid URIs/IDs intact."""
    resolved = []
    for item in track_list:
        item = item.strip()
        if not item:
            continue
        if item.startswith("spotify:track:") or (len(item) == 22 and item.isalnum()):
            resolved.append(item)
        else:
            try:
                res = sp.search(q=item, type="track", limit=1)
                tracks = res.get("tracks", {}).get("items", [])
                if tracks:
                    resolved.append(tracks[0]["uri"])
                else:
                    logger.warning(f"Could not resolve track: '{item}'")
            except Exception as e:
                logger.error(f"Error resolving track '{item}': {e}")
    return resolved

def _resolve_artists(sp, artist_list: list[str]) -> list[str]:
    """Resolves artist names to IDs/URIs, leaving valid IDs/URIs intact."""
    resolved = []
    for item in artist_list:
        item = item.strip()
        if not item:
            continue
        if item.startswith("spotify:artist:") or (len(item) == 22 and item.isalnum()):
            resolved.append(item)
        else:
            try:
                res = sp.search(q=item, type="artist", limit=1)
                artists = res.get("artists", {}).get("items", [])
                if artists:
                    resolved.append(artists[0]["id"])
                else:
                    logger.warning(f"Could not resolve artist: '{item}'")
            except Exception as e:
                logger.error(f"Error resolving artist '{item}': {e}")
    return resolved

# =====================================================================
# SYSTEM & AUTHENTICATION TOOLS
# =====================================================================

@mcp.tool()
def is_authenticated() -> str:
    """Check if the Spotify MCP server is currently authenticated and has access.
    
    Returns:
        A text description of the authentication status.
    """
    if auth.is_authenticated():
        try:
            sp = auth.get_spotify_client()
            user = sp.me()
            display_name = user.get("display_name", "Unknown")
            return f"Authenticated successfully as Spotify user: **{display_name}**"
        except Exception as e:
            return f"Authenticated, but failed to fetch user info: {str(e)}"
    else:
        return (
            "Not authenticated.\n"
            "To connect your Spotify account, please follow these steps:\n"
            "1. Call the `get_auth_url` tool to generate an authorization URL.\n"
            "2. Visit that URL in your browser and log in to Spotify.\n"
            "3. Once authorized, copy the full URL you were redirected to.\n"
            "4. Call the `complete_auth` tool and provide that URL as the `callback_url` parameter."
        )

@mcp.tool()
def get_auth_url() -> str:
    """Generate the Spotify OAuth URL for user authentication.
    
    Returns:
        The URL the user needs to visit to authorize Spotify access.
    """
    try:
        url = auth.get_auth_url()
        return (
            f"Please visit the following URL to authorize Spotify access:\n\n"
            f"{url}\n\n"
            "After authorizing, you will be redirected to localhost (which may show a page not found error). "
            "Copy the entire redirected URL from your browser's address bar and run the `complete_auth` "
            "tool with that URL."
        )
    except Exception as e:
        logger.exception("Error generating auth URL")
        return f"Error: {str(e)}"

@mcp.tool()
def complete_auth(callback_url: str) -> str:
    """Complete the Spotify authentication flow using the redirect URL from the browser.
    
    Args:
        callback_url: The full redirected URL (containing the code parameter) from the browser.
        
    Returns:
        Success or failure message.
    """
    return auth.complete_auth(callback_url)


# =====================================================================
# PLAYBACK CONTROL TOOLS
# =====================================================================

@mcp.tool()
@utils.spotify_tool_wrapper
def get_current_playback() -> str:
    """Get the current playback state of Spotify.
    
    Shows what track is playing, progress, active device, volume, and shuffle/repeat states.
    """
    sp = auth.get_spotify_client()
    state = sp.current_playback()
    return utils.format_playback_state(state)

@mcp.tool()
@utils.spotify_tool_wrapper
def play_track(track_name_or_uri: str, device_id: str = None) -> str:
    """Play a specific track on Spotify by name or Spotify track URI.
    
    If a name is provided, this searches Spotify and plays the top match.
    If a URI (e.g. 'spotify:track:...') is provided, it plays that track immediately.
    
    Args:
        track_name_or_uri: The track title (and optional artist) or the Spotify track URI.
        device_id: Optional. The ID of the Spotify device to play on.
    """
    sp = auth.get_spotify_client()
    
    if track_name_or_uri.startswith("spotify:track:"):
        track_uri = track_name_or_uri
        track_name = "Track from URI"
    else:
        # Search for the track first
        search_results = sp.search(q=track_name_or_uri, type="track", limit=1)
        tracks = search_results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"Could not find any tracks matching '{track_name_or_uri}'."
        
        track = tracks[0]
        track_uri = track.get("uri")
        artists = ", ".join([a.get("name") for a in track.get("artists", [])])
        track_name = f"'{track.get('name')}' by {artists}"
        
    sp.start_playback(device_id=device_id, uris=[track_uri])
    return f"Started playing {track_name}."

@mcp.tool()
@utils.spotify_tool_wrapper
def play_context(context_uri: str, device_id: str = None) -> str:
    """Play a Spotify context like an album, playlist, or artist by its Spotify URI.
    
    Args:
        context_uri: The Spotify URI of the album, playlist, or artist (e.g. 'spotify:album:...', 'spotify:playlist:...', 'spotify:artist:...').
        device_id: Optional. The ID of the Spotify device to play on.
    """
    sp = auth.get_spotify_client()
    sp.start_playback(device_id=device_id, context_uri=context_uri)
    return f"Playback started for context URI: `{context_uri}`."

@mcp.tool()
@utils.spotify_tool_wrapper
def pause_playback(device_id: str = None) -> str:
    """Pause the current Spotify playback.
    
    Args:
        device_id: Optional. The ID of the Spotify device to pause.
    """
    sp = auth.get_spotify_client()
    sp.pause_playback(device_id=device_id)
    return "Playback paused."

@mcp.tool()
@utils.spotify_tool_wrapper
def next_track(device_id: str = None) -> str:
    """Skip to the next track in the queue.
    
    Args:
        device_id: Optional. The ID of the Spotify device.
    """
    sp = auth.get_spotify_client()
    sp.next_track(device_id=device_id)
    return "Skipped to next track."

@mcp.tool()
@utils.spotify_tool_wrapper
def previous_track(device_id: str = None) -> str:
    """Go back to the previous track in the playback history.
    
    Args:
        device_id: Optional. The ID of the Spotify device.
    """
    sp = auth.get_spotify_client()
    sp.previous_track(device_id=device_id)
    return "Returned to previous track."

@mcp.tool()
@utils.spotify_tool_wrapper
def set_volume(volume_percent: int, device_id: str = None) -> str:
    """Set the volume level for Spotify playback.
    
    Args:
        volume_percent: The volume percentage to set (0 to 100).
        device_id: Optional. The ID of the Spotify device.
    """
    if not (0 <= volume_percent <= 100):
        return "Error: Volume must be between 0 and 100."
        
    sp = auth.get_spotify_client()
    sp.volume(volume_percent, device_id=device_id)
    return f"Volume set to {volume_percent}%."

@mcp.tool()
@utils.spotify_tool_wrapper
def get_available_devices() -> str:
    """List all available Spotify devices connected to the user's account.
    
    Shows active devices, types, names, and unique device IDs.
    """
    sp = auth.get_spotify_client()
    results = sp.devices()
    devices = results.get("devices", [])
    return utils.format_devices_list(devices)

@mcp.tool()
@utils.spotify_tool_wrapper
def transfer_playback(device_id: str, force_play: bool = True) -> str:
    """Transfer the current playback to a different device.
    
    Args:
        device_id: The unique ID of the target Spotify device.
        force_play: If True, playback starts on the new device immediately. If False, keeps current state (playing or paused).
    """
    sp = auth.get_spotify_client()
    sp.transfer_playback(device_id=device_id, force_play=force_play)
    return f"Transferred playback to device `{device_id}`."

@mcp.tool()
@utils.spotify_tool_wrapper
def toggle_shuffle(state: bool, device_id: str = None) -> str:
    """Turn shuffle mode on or off.
    
    Args:
        state: True to turn shuffle on, False to turn shuffle off.
        device_id: Optional. The ID of the Spotify device.
    """
    sp = auth.get_spotify_client()
    sp.shuffle(state=state, device_id=device_id)
    status = "enabled" if state else "disabled"
    return f"Shuffle mode {status}."

@mcp.tool()
@utils.spotify_tool_wrapper
def set_repeat_mode(state: str, device_id: str = None) -> str:
    """Set repeat mode for playback.
    
    Args:
        state: The repeat mode to set. Must be one of 'track', 'context', or 'off'.
        device_id: Optional. The ID of the Spotify device.
    """
    state_lower = state.lower()
    if state_lower not in ["track", "context", "off"]:
        return "Error: Repeat mode must be one of 'track', 'context', or 'off'."
        
    sp = auth.get_spotify_client()
    sp.repeat(state=state_lower, device_id=device_id)
    return f"Repeat mode set to '{state_lower}'."


# =====================================================================
# SEARCH & BROWSE TOOLS
# =====================================================================

@mcp.tool()
@utils.spotify_tool_wrapper
def search_spotify(q: str, type: str = "track", limit: int = 10) -> str:
    """Search Spotify for tracks, artists, albums, or playlists.
    
    Args:
        q: The search query (e.g. track name, artist, lyrics).
        type: The type of item to search for. Must be 'track', 'artist', 'album', or 'playlist'. Default is 'track'.
        limit: The number of results to return (max 50, default 10).
    """
    type_lower = type.lower()
    if type_lower not in ["track", "artist", "album", "playlist"]:
        return "Error: Search type must be one of 'track', 'artist', 'album', or 'playlist'."
        
    sp = auth.get_spotify_client()
    results = sp.search(q=q, type=type_lower, limit=limit)
    
    # Return formatted responses based on search type
    if type_lower == "track":
        tracks = results.get("tracks", {}).get("items", [])
        return f"### Search results for tracks: '{q}'\n\n" + utils.format_tracks_table(tracks)
        
    elif type_lower == "artist":
        artists = results.get("artists", {}).get("items", [])
        if not artists:
            return "No artists found."
        lines = ["| Name | Popularity | Followers | Genres | URI |", "|------|------------|-----------|--------|-----|"]
        for a in artists:
            name = a.get("name", "Unknown").replace("|", "\\|")
            popularity = f"{a.get('popularity', 0)}%"
            followers = f"{a.get('followers', {}).get('total', 0):,}"
            genres = ", ".join(a.get("genres", [])) or "None"
            uri = a.get("uri", "")
            lines.append(f"| {name} | {popularity} | {followers} | {genres} | `{uri}` |")
        return f"### Search results for artists: '{q}'\n\n" + "\n".join(lines)
        
    elif type_lower == "album":
        albums = results.get("albums", {}).get("items", [])
        if not albums:
            return "No albums found."
        lines = ["| Album Name | Artist(s) | Release Date | Tracks | URI |", "|------------|-----------|--------------|--------|-----|"]
        for alb in albums:
            name = alb.get("name", "Unknown").replace("|", "\\|")
            artists = ", ".join([art.get("name") for art in alb.get("artists", [])]).replace("|", "\\|")
            release = alb.get("release_date", "Unknown")
            tracks_count = alb.get("total_tracks", 0)
            uri = alb.get("uri", "")
            lines.append(f"| {name} | {artists} | {release} | {tracks_count} | `{uri}` |")
        return f"### Search results for albums: '{q}'\n\n" + "\n".join(lines)
        
    elif type_lower == "playlist":
        playlists = results.get("playlists", {}).get("items", [])
        return f"### Search results for playlists: '{q}'\n\n" + utils.format_playlists_list(playlists)

@mcp.tool()
@utils.spotify_tool_wrapper
def get_recommendations(genres: str = None, artists: str = None, tracks: str = None, limit: int = 10) -> str:
    """Get recommendations based on seed genres, artists, or tracks.
    
    You must provide at least one seed source, and a combined maximum of 5 seeds.
    Artists and tracks can be provided as names (e.g. 'Coldplay', 'Fix You') or Spotify URIs/IDs.
    
    Args:
        genres: Optional. A comma-separated list of seed genre names (e.g. 'rock,pop,jazz').
        artists: Optional. A comma-separated list of seed artist names, URIs, or IDs.
        tracks: Optional. A comma-separated list of seed track names, URIs, or IDs.
        limit: The number of recommendations to return (default 10).
    """
    sp = auth.get_spotify_client()
    
    seed_genres = [g.strip() for g in genres.split(",") if g.strip()] if genres else None
    
    raw_artists = [a.strip() for a in artists.split(",") if a.strip()] if artists else None
    seed_artists = _resolve_artists(sp, raw_artists) if raw_artists else None
    
    raw_tracks = [t.strip() for t in tracks.split(",") if t.strip()] if tracks else None
    seed_tracks = _resolve_tracks(sp, raw_tracks) if raw_tracks else None
    
    # Validation: Count seeds
    seeds_count = (len(seed_genres) if seed_genres else 0) + \
                  (len(seed_artists) if seed_artists else 0) + \
                  (len(seed_tracks) if seed_tracks else 0)
                  
    if seeds_count == 0:
        return "Error: You must provide at least one seed from genres, artists, or tracks."
    if seeds_count > 5:
        return f"Error: Spotify allows a maximum of 5 seeds total. You provided {seeds_count} seeds."
        
    results = sp.recommendations(
        seed_genres=seed_genres,
        seed_artists=seed_artists,
        seed_tracks=seed_tracks,
        limit=limit
    )
    
    recommended_tracks = results.get("tracks", [])
    return f"### Recommended Tracks\n\n" + utils.format_tracks_table(recommended_tracks)

@mcp.tool()
@utils.spotify_tool_wrapper
def get_featured_playlists(limit: int = 10) -> str:
    """List Spotify featured playlists (e.g. editorial and seasonal suggestions).
    
    Args:
        limit: Number of playlists to return (default 10).
    """
    sp = auth.get_spotify_client()
    results = sp.featured_playlists(limit=limit)
    message = results.get("message", "Featured Playlists")
    playlists = results.get("playlists", {}).get("items", [])
    return f"### {message}\n\n" + utils.format_playlists_list(playlists)


# =====================================================================
# LIBRARY & PLAYLIST TOOLS
# =====================================================================

@mcp.tool()
@utils.spotify_tool_wrapper
def get_user_playlists(limit: int = 20) -> str:
    """List the current user's library and collaborative playlists.
    
    Args:
        limit: Number of playlists to return (max 50, default 20).
    """
    sp = auth.get_spotify_client()
    results = sp.current_user_playlists(limit=limit)
    playlists = results.get("items", [])
    return "### Your Spotify Playlists\n\n" + utils.format_playlists_list(playlists)

@mcp.tool()
@utils.spotify_tool_wrapper
def create_playlist(name: str, description: str = "", public: bool = True) -> str:
    """Create a new playlist in the user's Spotify library.
    
    Args:
        name: The name of the new playlist.
        description: Optional. Short description of the playlist.
        public: If True, the playlist will be public. If False, it will be private.
    """
    sp = auth.get_spotify_client()
    
    playlist = sp.current_user_playlist_create(
        name=name,
        public=public,
        collaborative=False,
        description=description
    )
    
    playlist_name = playlist.get("name")
    playlist_uri = playlist.get("uri")
    return f"Successfully created playlist **{playlist_name}** | URI: `{playlist_uri}`"

@mcp.tool()
@utils.spotify_tool_wrapper
def add_to_playlist(playlist_id: str, track_uris: str) -> str:
    """Add one or more tracks to a Spotify playlist.
    
    Tracks can be provided as names (e.g. 'Fix You') or Spotify track URIs.
    
    Args:
        playlist_id: The ID or URI of the target playlist.
        track_uris: A comma-separated list of Spotify track URIs or names.
    """
    raw_list = [u.strip() for u in track_uris.split(",") if u.strip()]
    if not raw_list:
        return "Error: No track URIs or names provided."
        
    sp = auth.get_spotify_client()
    resolved_uris = _resolve_tracks(sp, raw_list)
    if not resolved_uris:
        return "Error: Could not resolve any of the provided tracks to Spotify URIs."
        
    sp.playlist_add_items(playlist_id=playlist_id, items=resolved_uris)
    return f"Successfully added {len(resolved_uris)} track(s) to playlist `{playlist_id}`."

@mcp.tool()
@utils.spotify_tool_wrapper
def get_playlist_tracks(playlist_id: str, limit: int = 50) -> str:
    """Get the list of tracks contained in a specific playlist.
    
    Args:
        playlist_id: The ID or URI of the playlist.
        limit: The number of tracks to fetch (max 100, default 50).
    """
    sp = auth.get_spotify_client()
    results = sp.playlist_items(playlist_id=playlist_id, limit=limit)
    tracks = results.get("items", [])
    return f"### Tracks in Playlist `{playlist_id}`\n\n" + utils.format_tracks_table(tracks)

@mcp.tool()
@utils.spotify_tool_wrapper
def get_user_saved_tracks(limit: int = 20) -> str:
    """Get tracks from the user's 'Liked Songs' library.
    
    Args:
        limit: Number of saved tracks to fetch (max 50, default 20).
    """
    sp = auth.get_spotify_client()
    results = sp.current_user_saved_tracks(limit=limit)
    tracks = results.get("items", [])
    return "### Your Liked Songs\n\n" + utils.format_tracks_table(tracks)

@mcp.tool()
@utils.spotify_tool_wrapper
def save_tracks(track_uris: str) -> str:
    """Add one or more tracks to the user's 'Liked Songs' library.
    
    Tracks can be provided as names (e.g. 'Fix You') or Spotify track URIs.
    
    Args:
        track_uris: A comma-separated list of Spotify track URIs, IDs, or names.
    """
    raw_list = [u.strip() for u in track_uris.split(",") if u.strip()]
    if not raw_list:
        return "Error: No track URIs or names provided."
        
    sp = auth.get_spotify_client()
    resolved_uris = _resolve_tracks(sp, raw_list)
    if not resolved_uris:
        return "Error: Could not resolve any of the provided tracks to Spotify URIs."
        
    sp.current_user_saved_tracks_add(tracks=resolved_uris)
    return f"Successfully added {len(resolved_uris)} track(s) to your Liked Songs."

@mcp.tool()
@utils.spotify_tool_wrapper
def remove_tracks(track_uris: str) -> str:
    """Remove one or more tracks from the user's 'Liked Songs' library.
    
    Tracks can be provided as names (e.g. 'Fix You') or Spotify track URIs.
    
    Args:
        track_uris: A comma-separated list of Spotify track URIs, IDs, or names.
    """
    raw_list = [u.strip() for u in track_uris.split(",") if u.strip()]
    if not raw_list:
        return "Error: No track URIs or names provided."
        
    sp = auth.get_spotify_client()
    resolved_uris = _resolve_tracks(sp, raw_list)
    if not resolved_uris:
        return "Error: Could not resolve any of the provided tracks to Spotify URIs."
        
    sp.current_user_saved_tracks_delete(tracks=resolved_uris)
    return f"Successfully removed {len(resolved_uris)} track(s) from your Liked Songs."

@mcp.tool()
def get_lyrics(song_title: str, artist_name: str = "") -> str:
    """Get the lyrics for a specific song from Genius.com.
    
    If the artist_name is not provided, the tool will try to search for the song_title alone.
    When presenting lyrics to the user, send the complete lyrics response in ONE message bubble.
    
    Args:
        song_title: The title of the song to search for.
        artist_name: Optional. The name of the artist of the song.
    """
    return utils.scrape_genius_lyrics(song_title, artist_name)


# =====================================================================
# SERVER RUNNER
# =====================================================================

if __name__ == "__main__":
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Run Spotify MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.getenv("FASTMCP_TRANSPORT", "stdio"),
        help="Transport protocol (stdio or sse)"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("FASTMCP_HOST", "0.0.0.0"),
        help="Host address to bind to for SSE transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FASTMCP_PORT", "8080")),
        help="Port to bind to for SSE transport (default: 8080)"
    )
    
    args = parser.parse_args()
    
    if args.transport == "sse":
        logger.info(f"Starting Spotify MCP server on SSE transport (http://{args.host}:{args.port}/sse)")
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        logger.info("Starting Spotify MCP server on stdio transport")
        mcp.run(transport="stdio")
