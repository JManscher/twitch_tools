"""Twitch API integration for fetching current stream game."""

import requests
from typing import Optional

import config


class TwitchAPIError(Exception):
    """Exception raised for Twitch API errors."""
    pass


def get_app_access_token() -> str:
    """Get an app access token using client credentials flow.
    
    Returns:
        The access token string
        
    Raises:
        TwitchAPIError: If token retrieval fails
    """
    url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": config.TWITCH_CLIENT_ID,
        "client_secret": config.TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as e:
        raise TwitchAPIError(f"Failed to get Twitch access token: {e}")
    except KeyError:
        raise TwitchAPIError("Invalid response from Twitch OAuth")


def get_current_game(channel_name: str) -> Optional[str]:
    """Get the current game being played on a Twitch channel.
    
    Args:
        channel_name: The Twitch channel login name (e.g., "channelname")
        
    Returns:
        The game name if the channel is live, None if offline
        
    Raises:
        TwitchAPIError: If the API request fails
    """
    # Get access token
    access_token = get_app_access_token()
    
    # Get stream info
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": config.TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "user_login": channel_name.lower()
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        streams = data.get("data", [])
        
        if not streams:
            # Channel is offline
            return None
        
        # Get game name from stream data
        game_name = streams[0].get("game_name")
        
        if not game_name:
            return None
            
        return game_name
        
    except requests.RequestException as e:
        raise TwitchAPIError(f"Failed to get stream info: {e}")


def get_channel_game() -> Optional[str]:
    """Get the current game for the configured Twitch channel.
    
    Returns:
        The game name if live, None if offline
    """
    return get_current_game(config.TWITCH_CHANNEL)
