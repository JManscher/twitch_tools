#!/usr/bin/env python3
"""
Mix It Up Game Command - Fetches Steam game statistics.

Usage:
    python game_command.py [game_name]
    
If game_name is provided, looks up stats for that game.
If omitted, fetches current game from Twitch stream.
"""

import sys

# Categories on Twitch that are not actual games (case-insensitive check)
NON_GAME_CATEGORIES = {
    "just chatting",
    "music",
    "art",
    "talk shows & podcasts",
    "asmr",
    "food & drink",
    "travel & outdoors",
    "special events",
    "sports",
    "fitness & health",
    "pools, hot tubs, and beaches",
    "makers & crafting",
    "software and game development",
    "science & technology",
    "beauty & body art",
    "i'm only sleeping",
}

# Handle the case where the script is run without dependencies installed
try:
    import config
    import steam_api
    import twitch_api
except ImportError as e:
    print(f"Error: Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)


def main():
    """Main entry point for the game command."""
    try:
        # Validate configuration
        config.validate_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    
    # Get game name from command line or Twitch
    game_name = None
    game_from_twitch = False
    if len(sys.argv) > 1:
        # Game name provided as argument (may be multiple words)
        game_name = " ".join(sys.argv[1:])
        
        # Handle Mix It Up passing literal "$arg1text" when no argument provided
        if game_name.startswith("$arg") and game_name.endswith("text"):
            game_name = None
    
    if game_name is None:
        # No argument - try to get current game from Twitch
        game_from_twitch = True
        try:
            game_name = twitch_api.get_channel_game()
            
            if not game_name:
                print("Channel is offline or no category is set. Please specify a game name.")
                sys.exit(0)
                
        except twitch_api.TwitchAPIError as e:
            print(f"Could not fetch Twitch stream: {e}")
            sys.exit(1)
    
    # Check if it's a non-game category (only relevant info if auto-detected from Twitch)
    if game_name.lower() in NON_GAME_CATEGORIES:
        if game_from_twitch:
            print(f'Currently in "{game_name}" - not a game. Please specify a game name.')
        else:
            print(f'"{game_name}" is not a game category.')
        sys.exit(0)
    
    # Get Steam stats for the game
    try:
        result = steam_api.get_game_stats(game_name)
        print(result)
    except steam_api.SteamAPIError as e:
        print(f"Steam API error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
