#!/usr/bin/env python3
"""
Mix It Up Game Command - Fetches Steam game statistics.

Usage:
    python game_command.py [game_name]
    
If game_name is provided, looks up stats for that game.
If omitted, fetches current game from Twitch stream.
"""

import sys

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
    if len(sys.argv) > 1:
        # Game name provided as argument (may be multiple words)
        game_name = " ".join(sys.argv[1:])
    else:
        # No argument - try to get current game from Twitch
        try:
            game_name = twitch_api.get_channel_game()
            
            if not game_name:
                print("Channel is offline. Please specify a game name.")
                sys.exit(0)
                
        except twitch_api.TwitchAPIError as e:
            print(f"Could not fetch Twitch stream: {e}")
            sys.exit(1)
    
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
