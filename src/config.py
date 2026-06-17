import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging to write to stderr so as not to pollute stdout (which is used for MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("spotify_mcp.config")

# Find the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load dotenv from project root
dotenv_path = PROJECT_ROOT / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
    logger.info(f"Loaded environment variables from {dotenv_path}")
else:
    # Also attempt loading from the current working directory as fallback
    load_dotenv()

# Spotify API Configuration
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8080/callback")

# Cache path for the token
CACHE_PATH = os.getenv("SPOTIPY_CACHE_PATH")
if not CACHE_PATH:
    CACHE_PATH = str(PROJECT_ROOT / ".spotify_token_cache")

# Validate configuration
def check_config():
    missing = []
    if not CLIENT_ID:
        missing.append("SPOTIPY_CLIENT_ID")
    if not CLIENT_SECRET:
        missing.append("SPOTIPY_CLIENT_SECRET")
    
    if missing:
        logger.warning(
            f"Missing required Spotify credentials: {', '.join(missing)}. "
            f"Please create a .env file at {dotenv_path} or set them in your environment. "
            f"Authentication tools will be available, but other tools will fail until credentials are provided."
        )
        return False
    return True

# Run check on import
IS_CONFIGURED = check_config()
