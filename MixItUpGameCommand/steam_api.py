"""Steam Web API integration for fetching game statistics."""

import requests
from datetime import datetime
from typing import Optional, Tuple
from difflib import SequenceMatcher

import config


class SteamAPIError(Exception):
    """Exception raised for Steam API errors."""
    pass


def resolve_vanity_url(vanity_url: str) -> str:
    """Resolve a Steam vanity URL to a Steam64 ID.
    
    Args:
        vanity_url: The vanity URL name (e.g., "username")
        
    Returns:
        The Steam64 ID as a string
        
    Raises:
        SteamAPIError: If the vanity URL cannot be resolved
    """
    url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
    params = {
        "key": config.STEAM_API_KEY,
        "vanityurl": vanity_url
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("response", {}).get("success") == 1:
            return data["response"]["steamid"]
        else:
            raise SteamAPIError(f"Could not resolve Steam profile: {vanity_url}")
    except requests.RequestException as e:
        raise SteamAPIError(f"Steam API request failed: {e}")


def get_owned_games(steam_id: str) -> list:
    """Get list of owned games with playtime information.
    
    Args:
        steam_id: The Steam64 ID
        
    Returns:
        List of game dictionaries with appid, name, playtime_forever, rtime_last_played
    """
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": config.STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return data.get("response", {}).get("games", [])
    except requests.RequestException as e:
        raise SteamAPIError(f"Failed to fetch owned games: {e}")


def get_achievements(steam_id: str, app_id: int) -> Tuple[int, int]:
    """Get achievement progress for a specific game.
    
    Args:
        steam_id: The Steam64 ID
        app_id: The Steam application ID
        
    Returns:
        Tuple of (unlocked_count, total_count)
        Returns (0, 0) if the game has no achievements or stats are private
    """
    url = "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    params = {
        "key": config.STEAM_API_KEY,
        "steamid": steam_id,
        "appid": app_id
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        # 400 errors often mean no achievements for this game
        if response.status_code == 400:
            return (0, 0)
            
        response.raise_for_status()
        data = response.json()
        
        if not data.get("playerstats", {}).get("success"):
            return (0, 0)
        
        achievements = data.get("playerstats", {}).get("achievements", [])
        if not achievements:
            return (0, 0)
            
        total = len(achievements)
        unlocked = sum(1 for a in achievements if a.get("achieved") == 1)
        
        return (unlocked, total)
    except requests.RequestException:
        return (0, 0)


def find_game_by_name(games: list, search_name: str) -> Optional[dict]:
    """Find a game in the owned games list by name using fuzzy matching.
    
    Args:
        games: List of game dictionaries from get_owned_games
        search_name: The game name to search for
        
    Returns:
        The matching game dictionary, or None if not found
    """
    search_lower = search_name.lower().strip()
    
    # First try exact match (case-insensitive)
    for game in games:
        if game.get("name", "").lower() == search_lower:
            return game
    
    # Then try contains match
    for game in games:
        if search_lower in game.get("name", "").lower():
            return game
    
    # Finally try fuzzy matching with a reasonable threshold
    best_match = None
    best_ratio = 0.6  # Minimum threshold
    
    for game in games:
        game_name = game.get("name", "").lower()
        ratio = SequenceMatcher(None, search_lower, game_name).ratio()
        
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = game
    
    return best_match


def format_playtime(minutes: int) -> str:
    """Format playtime from minutes to a readable string."""
    hours = minutes / 60
    if hours < 1:
        return f"{minutes} mins"
    elif hours < 10:
        return f"{hours:.1f} hrs"
    else:
        return f"{int(hours)} hrs"


def format_last_played(timestamp: int) -> str:
    """Format Unix timestamp to a readable date."""
    if not timestamp:
        return "Unknown"
    
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%b %d, %Y")
    except (ValueError, OSError):
        return "Unknown"


def get_steam_id() -> str:
    """Get Steam ID from either direct ID or vanity URL.
    
    Returns:
        The Steam64 ID as a string
        
    Raises:
        SteamAPIError: If neither Steam ID nor vanity URL is configured
    """
    # Check if direct Steam ID is provided
    if config.STEAM_ID_URL:
        return config.STEAM_ID_URL
    
    # Fall back to vanity URL resolution
    if config.STEAM_VANITY_URL:
        return resolve_vanity_url(config.STEAM_VANITY_URL)
    
    raise SteamAPIError("Neither STEAM_ID_URL nor STEAM_VANITY_URL is configured")


def get_game_stats(game_name: str) -> str:
    """Get formatted game statistics for a given game name.
    
    Args:
        game_name: The name of the game to look up
        
    Returns:
        Formatted string with game statistics
    """
    # Get Steam ID (from direct ID or vanity URL)
    steam_id = get_steam_id()
    
    # Get owned games
    games = get_owned_games(steam_id)
    
    if not games:
        return "No games found in Steam library (profile may be private)."
    
    # Find the game
    game = find_game_by_name(games, game_name)
    
    if not game:
        return f'Game "{game_name}" not found in Steam library.'
    
    # Get game info
    name = game.get("name", "Unknown")
    playtime = format_playtime(game.get("playtime_forever", 0))
    last_played = format_last_played(game.get("rtime_last_played", 0))
    
    # Get achievements
    unlocked, total = get_achievements(steam_id, game["appid"])
    
    # Format output
    if total > 0:
        return f"{name} - Playtime: {playtime} | Achievements: {unlocked}/{total} | Last Played: {last_played}"
    else:
        return f"{name} - Playtime: {playtime} | Last Played: {last_played}"
