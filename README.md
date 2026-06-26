# Spotify Model Context Protocol (MCP) Server

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square" alt="Python Version">
  <img src="https://img.shields.io/badge/Framework-FastMCP-green.svg?style=flat-square" alt="FastMCP">
  <img src="https://img.shields.io/badge/API-Spotify%20Web-1DB954?style=flat-square&logo=spotify" alt="Spotify API">
  <img src="https://img.shields.io/badge/MCP-Compatible-orange.svg?style=flat-square" alt="MCP Compatible">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey.svg?style=flat-square" alt="License">
</p>

A robust, production-grade Model Context Protocol (MCP) server that connects Spotify playback, search, and library management directly to LLM Agents (such as Cursor, Claude Desktop, and other MCP clients).

Built in Python using **FastMCP** and **Spotipy**, this server includes connection pooling, log isolation, and a custom dual-authentication strategy to ensure long-term stability and compatibility with non-interactive agents.

---

## Features

- **Playback Control**: Play tracks/albums/playlists, pause, skip, adjust volume, toggle shuffle/repeat, and transfer playback between devices.
- **Search & Discovery**: Search tracks, artists, albums, and playlists, and get tailored music recommendations based on genres/artists.
- **Library Management**: View and modify your "Liked Songs" library and create/manage playlists.
- **Dual Authentication**: Local web redirect or manual copy-paste fallback designed to run seamlessly through the agent interface.
- **Robust Connection Handling**: Connection pooling via `requests.Session` and thread-safe automatic token refreshing to prevent memory leaks and credentials expiration crashes.
- **Log Safety**: All server logs and debug outputs are isolated to `stderr`, leaving `stdout` purely for MCP protocol messages.

---

## Setup & Configuration

### Prerequisites
- Python 3.10+
- A Spotify account (Spotify Premium is required for playback control features).

### 1. Register Spotify App
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**.
3. Name your app (e.g., "My MCP Spotify Server") and add a description.
4. In the **Redirect URIs** field, enter:
   `http://127.0.0.1:8080/callback`
5. Check the box for "Web API" under the APIs to request.
6. Click **Save**.
7. In the settings page of your new app, retrieve the **Client ID** and **Client Secret**.

### 2. Configure Environment Variables
Create a file named `.env` in the root of the `Spotify MCP` folder:

```env
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8080/callback
```

---

## Installation & Running

Ensure you have created the virtual environment and installed dependencies:

```bash
cd "Spotify MCP"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Server Locally
To run and inspect the server using the MCP CLI tool:

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the dev inspector
mcp dev src/server.py
```

---

## Client Integration

Add the server to your MCP client configuration (e.g., Cursor, Claude Desktop, or custom MCP client).

For example, in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "spotify": {
      "command": "/root/Spotify MCP/.venv/bin/python",
      "args": [
        "-m",
        "src.server"
      ],
      "env": {
        "SPOTIPY_CLIENT_ID": "your_spotify_client_id",
        "SPOTIPY_CLIENT_SECRET": "your_spotify_client_secret",
        "SPOTIPY_REDIRECT_URI": "http://127.0.0.1:8080/callback"
      }
    }
  }
}
```

---

## Authentication Flow

Because MCP servers run in background processes without terminal input, the server supports a smooth **dual-authentication** flow:

### Flow 1: Automated Local Redirect (Default)
When starting up, if credentials are set but not authorized:
1. The server can attempt to open a browser to log you in.
2. Once authorized, the Spotify callback redirects to `http://127.0.0.1:8080/callback?code=...` which is processed, and tokens are written to `.spotify_token_cache` in the project root.

### Flow 2: Interactive LLM/Agent Authorization (Recommended fallback)
If Flow 1 is blocked or you are running the agent on a remote environment:
1. The agent will call the `get_auth_url` tool.
2. The agent will display the Spotify login URL to you in the chat.
3. Open the link, log in, authorize, and copy the final URL you redirect to (e.g., `http://127.0.0.1:8080/callback?code=...`).
4. Paste this URL back to the agent.
5. The agent calls the `complete_auth(callback_url)` tool.
6. The server finishes the auth flow, caches the tokens, and immediately gains access!

---

## Available Tools

The server exposes 25 tools categorized as follows:

| Category | Tool | Description |
| :--- | :--- | :--- |
| **System** | `is_authenticated` | Verifies connection status and logged-in user profile. |
| | `get_auth_url` | Generates the login URL to authorize Spotify. |
| | `complete_auth` | Validates callback redirect and stores tokens. |
| **Playback** | `get_current_playback` | Shows what's playing, active device, progress bar, volume, etc. |
| | `play_track` | Plays a track by name search or exact URI. |
| | `play_context` | Plays an album, playlist, or artist by URI. |
| | `pause_playback` | Pauses Spotify. |
| | `next_track` | Skips to the next song in the queue. |
| | `previous_track` | Plays the previous song in history. |
| | `set_volume` | Sets volume level (0 to 100). |
| | `get_available_devices` | Lists connected Spotify clients with their status and IDs. |
| | `transfer_playback` | Switches active playback to another device ID. |
| | `toggle_shuffle` | Toggles shuffle state. |
| | `set_repeat_mode` | Sets repeat mode ('track', 'context', 'off'). |
| **Search** | `search_spotify` | Searches for tracks, albums, artists, or playlists. |
| | `get_recommendations` | Recommends tracks based on seed genres, artists, or tracks. |
| | `get_featured_playlists` | Retrieves current Spotify editorial featured playlists. |
| | `get_lyrics` | Retrieves song lyrics from Genius.com via web scraping; agents should send the complete lyrics response in ONE message bubble. |
| **Library** | `get_user_playlists` | Lists playlists in the user's library. |
| | `create_playlist` | Creates a new playlist. |
| | `add_to_playlist` | Adds tracks (comma-separated URIs) to a playlist. |
| | `get_playlist_tracks` | Lists tracks in a specific playlist. |
| | `get_user_saved_tracks` | Lists Liked Songs. |
| | `save_tracks` | Adds tracks to Liked Songs. |
| | `remove_tracks` | Removes tracks from Liked Songs. |

---

*Project created with **Gemini Antigravity**, with much love. ❤️*
