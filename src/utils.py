import functools
import logging
import time
from spotipy import SpotifyException
from requests import RequestException

logger = logging.getLogger("spotify_mcp.utils")

def spotify_tool_wrapper(func):
    """Decorator to wrap Spotify MCP tools.
    Handles rate limiting (HTTP 429) automatically, catches connection and permission errors,
    and formats exceptions into clean messages returned to the agent instead of crashing the server.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        backoff_base = 2
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except SpotifyException as e:
                # 429: Rate Limit
                if e.http_status == 429:
                    retry_after = 5  # Default fallback wait
                    if e.headers and 'Retry-After' in e.headers:
                        try:
                            retry_after = int(e.headers['Retry-After'])
                        except ValueError:
                            pass
                    logger.warning(
                        f"Spotify API rate limit (429) hit in {func.__name__}. "
                        f"Retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})."
                    )
                    time.sleep(retry_after)
                    continue
                
                # Check for restricted operations (e.g. playback control requires Premium or active device)
                if e.http_status == 403:
                    logger.error(f"Access forbidden (403) in {func.__name__}: {e.msg}")
                    return (
                        f"Spotify Error (403 Forbidden): {e.msg}\n"
                        "Note: Playback control tools require a Spotify Premium subscription and "
                        "correct authorization scopes. If you are modifying a playlist, make sure "
                        "you own it or it is collaborative."
                    )
                
                if e.http_status == 404:
                    logger.error(f"Not found (404) in {func.__name__}: {e.msg}")
                    if "No active device" in e.msg:
                        return (
                            "Spotify Error (404 Not Found): No active device detected.\n"
                            "Please open Spotify on your device (phone, computer, smart speaker, etc.) "
                            "and play a track, or use the `get_available_devices` and `transfer_playback` "
                            "tools to activate a device."
                        )
                    return f"Spotify Error (404 Not Found): {e.msg}"
                
                logger.error(f"Spotify API exception in {func.__name__}: {e}")
                return f"Spotify API Error: {e.msg} (Status code: {e.http_status})"
            
            except RequestException as e:
                logger.error(f"Network error in {func.__name__}: {e}")
                if attempt < max_retries - 1:
                    sleep_time = backoff_base ** attempt
                    logger.info(f"Retrying network request in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                return (
                    f"Network Connection Error: Could not connect to Spotify Web API.\n"
                    f"Detail: {str(e)}"
                )
            
            except RuntimeError as e:
                logger.error(f"Runtime configuration/auth error in {func.__name__}: {e}")
                return str(e)
            
            except Exception as e:
                logger.exception(f"Unexpected error in tool {func.__name__}")
                return f"Unexpected Server Error: {str(e)}"
        
        return "Error: Request failed repeatedly due to transient connection issues or rate limiting."
    
    return wrapper

def format_duration(ms: int) -> str:
    """Formats milliseconds into MM:SS format."""
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    hours = int((ms / (1000 * 60 * 60)) % 24)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def format_tracks_table(tracks: list) -> str:
    """Formats a list of track objects as a markdown table."""
    if not tracks:
        return "No tracks found."
    
    lines = [
        "| # | Track Name | Artist(s) | Album | Duration | URI |",
        "|---|------------|-----------|-------|----------|-----|"
    ]
    for idx, item in enumerate(tracks, 1):
        # Handle nesting: items from playlist/library can be under "item" or "track"
        track = None
        if isinstance(item, dict):
            if "item" in item and isinstance(item["item"], dict):
                track = item["item"]
            elif "track" in item and isinstance(item["track"], dict):
                track = item["track"]
        
        if not track:
            track = item
            
        if not track or not isinstance(track, dict):
            continue
            
        name = track.get("name", "Unknown Track").replace("|", "\\|")
        artists = ", ".join([a.get("name", "Unknown").replace("|", "\\|") for a in track.get("artists", [])])
        album = track.get("album", {}).get("name", "Unknown").replace("|", "\\|")
        duration = format_duration(track.get("duration_ms", 0))
        uri = track.get("uri", "")
        
        lines.append(f"| {idx} | {name} | {artists} | {album} | {duration} | `{uri}` |")
        
    return "\n".join(lines)

def format_playlists_list(playlists: list) -> str:
    """Formats a list of playlist objects as a markdown table."""
    if not playlists:
        return "No playlists found."
        
    lines = [
        "| Name | Owner | Tracks | Public | URI |",
        "|------|-------|--------|--------|-----|"
    ]
    for playlist in playlists:
        name = playlist.get("name", "Unnamed Playlist").replace("|", "\\|")
        owner = playlist.get("owner", {}).get("display_name", "Unknown").replace("|", "\\|")
        tracks_count = playlist.get("tracks", {}).get("total", 0)
        is_public = "Yes" if playlist.get("public") else "No"
        uri = playlist.get("uri", "")
        
        lines.append(f"| {name} | {owner} | {tracks_count} | {is_public} | `{uri}` |")
        
    return "\n".join(lines)

def format_devices_list(devices: list) -> str:
    """Formats a list of device objects as a markdown table."""
    if not devices:
        return "No Spotify devices detected. Please ensure Spotify is running on at least one device."
        
    lines = [
        "| Active | Device Name | Type | Volume | ID |",
        "|--------|-------------|------|--------|----|"
    ]
    for d in devices:
        is_active = "🟢 Yes" if d.get("is_active") else "⚪ No"
        name = d.get("name", "Unknown Device").replace("|", "\\|")
        device_type = d.get("type", "Unknown")
        volume = f"{d.get('volume_percent', 0)}%"
        dev_id = d.get("id", "Restricted")
        
        lines.append(f"| {is_active} | {name} | {device_type} | {volume} | `{dev_id}` |")
        
    return "\n".join(lines)

def format_playback_state(state: dict) -> str:
    """Formats current playback state into a detailed markdown block."""
    if not state:
        return (
            "### Spotify Playback State\n\n"
            "**Status**: No active playback detected.\n\n"
            "*Note: Please open Spotify on your phone/computer and start playing a track, "
            "or use the `get_available_devices` and `transfer_playback` tools to activate a device.*"
        )
        
    is_playing = state.get("is_playing", False)
    device = state.get("device", {})
    device_name = device.get("name", "Unknown Device")
    device_type = device.get("type", "Unknown")
    volume = device.get("volume_percent", 0)
    
    shuffle_state = "On" if state.get("shuffle_state") else "Off"
    repeat_state = state.get("repeat_state", "off").capitalize()
    
    item = state.get("item")
    if not item:
        return (
            f"### Spotify Playback State\n\n"
            f"Device: **{device_name}** ({device_type}) | Volume: {volume}%\n"
            f"Playback status: Paused or inactive (No track selected)."
        )
        
    track_name = item.get("name", "Unknown Track")
    artists = ", ".join([a.get("name", "Unknown") for a in item.get("artists", [])])
    album = item.get("album", {}).get("name", "Unknown Album")
    duration_ms = item.get("duration_ms", 0)
    progress_ms = state.get("progress_ms", 0)
    
    progress_str = format_duration(progress_ms)
    duration_str = format_duration(duration_ms)
    
    # Create visual progress bar (20 chars long)
    bar_length = 20
    if duration_ms > 0:
        filled = int((progress_ms / duration_ms) * bar_length)
    else:
        filled = 0
    bar = "█" * filled + "░" * (bar_length - filled)
    
    status_icon = "▶️ Playing" if is_playing else "⏸️ Paused"
    
    lines = [
        "### Spotify Playback State",
        f"**{status_icon}** on **{device_name}** ({device_type}) | Volume: {volume}%",
        "",
        f"🎵 **{track_name}**",
        f"👤 **Artists**: {artists}",
        f"💿 **Album**: {album}",
        f"⏱️ `{progress_str}` {bar} `{duration_str}`",
        "",
        f"🔀 **Shuffle**: {shuffle_state} | 🔁 **Repeat**: {repeat_state}",
        f"🔗 **URI**: `{item.get('uri', '')}`"
    ]
    
    return "\n".join(lines)


def scrape_genius_lyrics(song_title: str, artist_name: str = "") -> str:
    """Scrapes lyrics from Genius.com without requiring an API key."""
    import requests
    from bs4 import BeautifulSoup
    import urllib.parse
    import re
    
    query = f"{song_title} {artist_name}".strip()
    logger.info(f"Searching Genius lyrics for query: '{query}'")
    
    # 1. Search Genius songs endpoint
    search_url = f"https://genius.com/api/search/song?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        r.raise_for_status()
        search_results = r.json()
    except Exception as e:
        logger.error(f"Failed to query Genius search API: {e}")
        return f"Error: Failed to query Genius search API: {str(e)}"
        
    # Extract song hits
    hits = []
    try:
        sections = search_results.get("response", {}).get("sections", [])
        for section in sections:
            if section.get("type") == "song":
                hits = section.get("hits", [])
                break
    except Exception as e:
        logger.error(f"Error parsing Genius search results structure: {e}")
        
    if not hits:
        return f"Could not find any song lyrics on Genius matching query: '{query}'."
        
    # Get top hit song details
    top_hit = hits[0].get("result", {})
    song_url = top_hit.get("url")
    full_title = top_hit.get("full_title")
    
    if not song_url:
        return f"Could not retrieve lyrics URL for: '{full_title}'."
        
    logger.info(f"Found song page on Genius: {song_url}")
    
    # 2. Fetch lyrics page
    try:
        r = requests.get(song_url, headers=headers, timeout=10)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        logger.error(f"Failed to fetch Genius page {song_url}: {e}")
        return f"Error: Failed to fetch lyrics page from Genius: {str(e)}"
        
    # 3. Parse HTML
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Genius lyrics are typically stored in div[class^="Lyrics__Container"]
        lyrics_divs = soup.select('div[class^="Lyrics__Container"]')
        
        # Fallback to older container class if needed
        if not lyrics_divs:
            lyrics_divs = soup.select('.song_body-lyrics p')
            
        if not lyrics_divs:
            # Check if it is an instrumental song
            if "instrumental" in html.lower() and "lyrics" not in html.lower():
                return f"### {full_title}\n\n*This song is instrumental (no lyrics).* \n\nSource: [Genius]({song_url})"
            return f"Could not find lyrics container on the webpage for: '{full_title}'. Genius might have changed their layout."
            
        # Extract and format text from all containers
        lyrics_parts = []
        for div in lyrics_divs:
            # Replace <br> tags with newlines
            for br in div.find_all("br"):
                br.replace_with("\n")
            
            # Extract clean text with newlines
            text = div.get_text()
            if text:
                lyrics_parts.append(text.strip())
                
        full_lyrics = "\n\n".join(lyrics_parts)
        
        # Clean up double/triple newlines
        full_lyrics = re.sub(r'\n{3,}', '\n\n', full_lyrics)
        
        return f"### {full_title}\n\n{full_lyrics}\n\n---\n*Source: [Genius]({song_url})*"
        
    except Exception as e:
        logger.exception("Error parsing lyrics from Genius HTML")
        return f"Error: Failed to parse lyrics from Genius page: {str(e)}"
