# Mix It Up Game Command

A CLI tool that fetches Steam game statistics for use with Mix It Up's `/game` Twitch command. Automatically retrieves playtime, achievements, and last played information from your Steam library.

## Features

- 🎮 Look up Steam playtime, achievements, and last played date for any game
- 🔴 Auto-detect current game from Twitch stream when no game is specified
- 🔍 Fuzzy game name matching (handles typos and partial names)
- ⚡ Supports both Steam vanity URLs and direct Steam64 IDs
- 🤖 Easy integration with Mix It Up for Twitch chat commands

## Output Examples

```
Elden Ring - Playtime: 142.5 hrs | Achievements: 28/42 | Last Played: Apr 5, 2026
```

```
Stardew Valley - Playtime: 87.2 hrs | Last Played: Mar 28, 2026
```

## Setup Instructions

### 1. Install Python

Download and install Python 3.8+ from [python.org](https://www.python.org/downloads/)

During installation, **check "Add Python to PATH"**.

### 2. Install Dependencies

Open a command prompt in this folder and run:

```cmd
pip install -r requirements.txt
```

### 3. Get a Steam API Key

1. Go to [Steam Web API Key](https://steamcommunity.com/dev/apikey)
2. Log in with your Steam account
3. Enter any domain name (e.g., `localhost`)
4. Copy the API key

### 4. Get Twitch App Credentials

1. Go to [Twitch Developer Console](https://dev.twitch.tv/console/apps)
2. Log in with your Twitch account
3. Click "Register Your Application"
4. Fill in:
   - **Name:** Something like "GameStatsBot" (must be unique)
   - **OAuth Redirect URLs:** `http://localhost`
   - **Category:** Chat Bot
5. Click "Create"
6. Click "Manage" on your new application
7. Copy the **Client ID**
8. Click "New Secret" and copy the **Client Secret**

### 5. Configure the Application

1. Copy `.env.example` to `.env`:
   ```cmd
   copy .env.example .env
   ```

2. Edit `.env` with your API keys and channel info:
   ```
   STEAM_API_KEY=your_actual_steam_api_key
   TWITCH_CLIENT_ID=your_actual_client_id
   TWITCH_CLIENT_SECRET=your_actual_client_secret
   TWITCH_CHANNEL=your_channel_name
   ```

3. Configure your Steam profile identifier (choose one):
   - **Option A:** Use your Steam vanity URL (e.g., `STEAM_VANITY_URL=yourname`)
   - **Option B:** Use your Steam64 ID directly (e.g., `STEAM_ID_URL=76561197960435530`)
   
   If both are provided, `STEAM_ID_URL` takes priority. Using the direct Steam64 ID skips the vanity URL resolution step.

### 6. Make Steam Profile Public

For the tool to access game stats, the Steam profile's **Game details** must be public:

1. Go to [Steam Privacy Settings](https://steamcommunity.com/my/edit/settings)
2. Set **Game details** to "Public"

### 7. Test the Command

```cmd
python game_command.py Elden Ring
```

You should see output like:
```
Elden Ring - Playtime: 142.5 hrs | Achievements: 28/42 | Last Played: Apr 5, 2026
```

## Mix It Up Integration

### Setting up the External Program

1. Open Mix It Up
2. Go to **Commands** → **Chat Commands**
3. Create a new command:
   - **Name:** `!game` or `/game`
   - **Trigger:** `!game` (or whatever you prefer)

4. Add an **External Program** action:
   - **File Path:** `C:\Path\To\Your\MixItUpGameCommand\game.bat`
   - **Arguments:** `$arg1text`
   - **Wait for finish:** Yes
   - **Show window:** No

5. Add a **Chat** action after the External Program:
   - **Message:** `$externalprogramresult`

### How It Works

- `/game Elden Ring` → Looks up "Elden Ring" stats
- `/game` (no argument) → Gets current game from Twitch stream, then looks up stats

### Troubleshooting Mix It Up

If the command doesn't work:

1. **Test the batch file manually:**
   ```cmd
   C:\Path\To\Your\MixItUpGameCommand\game.bat Elden Ring
   ```

2. **Check the .env file exists** and has valid API keys

3. **Make sure Python is in PATH:**
   ```cmd
   python --version
   ```

4. **Check Mix It Up logs** for any error messages

## Files

| File | Description |
|------|-------------|
| `game_command.py` | Main CLI entry point |
| `steam_api.py` | Steam Web API integration |
| `twitch_api.py` | Twitch API integration |
| `config.py` | Configuration management |
| `game.bat` | Windows batch wrapper for Mix It Up |
| `.env` | Your API keys (create from `.env.example`) |

## Privacy Note

Your Steam API key and Twitch credentials are stored locally in the `.env` file and never shared. The Steam profile's game details must be public for the tool to work.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## Support

If you encounter any issues or have questions, please [open an issue](https://github.com/yourusername/MixItUpGameCommand/issues) on GitHub.
