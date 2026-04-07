"""Configuration management for the game command."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Steam Configuration
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_VANITY_URL = os.getenv("STEAM_VANITY_URL")
STEAM_ID_URL = os.getenv("STEAM_ID_URL")  # Direct Steam64 ID as alternative to vanity URL

# Twitch Configuration
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")


def validate_config():
    """Validate that all required configuration is present."""
    missing = []
    
    if not STEAM_API_KEY:
        missing.append("STEAM_API_KEY")
    if not STEAM_VANITY_URL and not STEAM_ID_URL:
        missing.append("STEAM_VANITY_URL or STEAM_ID_URL")
    if not TWITCH_CLIENT_ID:
        missing.append("TWITCH_CLIENT_ID")
    if not TWITCH_CLIENT_SECRET:
        missing.append("TWITCH_CLIENT_SECRET")
    if not TWITCH_CHANNEL:
        missing.append("TWITCH_CHANNEL")
    
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    
    return True
