# Mix It Up Ask Command

A Magic-8-Ball-style Twitch command powered by [Scryfall](https://scryfall.com/). Viewers type `!ask <question>` and the bot answers with:

- A classic Magic-8-Ball verdict (e.g. `IT IS CERTAIN`, `OUTLOOK NOT SO GOOD`) in chat.
- A random Magic: The Gathering card image downloaded to a local file, ready for a Mix It Up Image Overlay to pop on screen.

The question text is accepted but ignored — like a real Magic 8-Ball, the cards decide.

## Features

- Random card draw via Scryfall's `/cards/random` endpoint (no API key required)
- Each run writes a fresh `card-<timestamp>.jpg` so the Mix It Up overlay can never cache an old image
- Old card images are pruned automatically — keeps only the 5 most recent (configurable)
- Verdict is derived deterministically from the card ID — same card always gives the same verdict
- Optional `DEBUG_TIMING` flag prints per-step timings to stderr

## Output

Two lines on stdout:

```
The cards say IT IS CERTAIN — Lightning Bolt
C:\Path\To\MixItUpMagic8CardCommand\card-1737654321123.jpg
```

A pointer file `latest_card_path.txt` is also written next to the script (or in `IMAGE_OUTPUT_DIR`) containing just the absolute path to the newest card image — useful for Mix It Up File Read wiring.

On failure:

```
The cards are silent (random card request failed: ...).
```

## Setup Instructions

### 1. Install Python

Download and install Python 3.8+ from [python.org](https://www.python.org/downloads/) and check **Add Python to PATH** during install.

### 2. Install Dependencies

Open a command prompt in this folder and run:

```cmd
pip install -r requirements.txt
```

### 3. Configure (optional)

Copy `.env.example` to `.env` only if you want to override defaults:

```cmd
copy .env.example .env
```

Available settings:

| Variable | Default | Purpose |
|---|---|---|
| `IMAGE_OUTPUT_DIR` | Script's own directory | Where `card-<timestamp>.jpg` images and `latest_card_path.txt` are written. |
| `KEEP_IMAGES` | `5` | How many recent card images to retain. Older ones are pruned each run. Minimum 1. |
| `DEBUG_TIMING` | `false` | Set to `true` to print per-step timing to stderr. |

### 4. Test the Command

```cmd
python ask_command.py will today be lucky
```

You should see two stdout lines (verdict + image path), a fresh `card-<timestamp>.jpg` next to the script, and `latest_card_path.txt` containing that path.

## Mix It Up Integration

### Why a fresh filename each run

Mix It Up's Image Overlay loads files via a `file://` URL and the embedded browser caches by URL. If we re-wrote the same `latest_card.jpg` every time, the overlay would often keep showing the previous card. Writing `card-<timestamp>.jpg` instead gives every draw a unique path and forces the overlay to redraw.

That means your overlay action needs a **dynamic** path. Two ways to wire that, pick whichever fits your Mix It Up version.

### Wiring option A — multi-line stdout

The script prints chat message on line 1 and the new image path on line 2. If your Mix It Up version exposes each captured line separately (often `$externalprogramresult1`, `$externalprogramresult2`):

1. **External Program**
   - **File Path:** `C:\Path\To\Your\MixItUpMagic8CardCommand\ask.bat`
   - **Arguments:** `$arg1text`
   - **Wait for finish:** Yes
   - **Show window:** No
2. **Chat**
   - **Message:** `$externalprogramresult1` (or whatever identifier maps to the first line)
3. **Overlay → Show Image**
   - **Image Path:** `$externalprogramresult2`

### Wiring option B — pointer file (most robust)

Every run also overwrites `latest_card_path.txt` with the absolute path to the new image. If you use Mix It Up's File Read action you don't have to rely on multi-line capture at all.

1. **External Program**
   - As above. `$externalprogramresult` ends up being the multi-line output; we'll only consume the first line for chat.
2. **Chat**
   - **Message:** `$externalprogramresult`
   - (Mix It Up will post the first line as the chat message; the trailing path line is harmless but if you want it stripped, use a Text/Replace action on `\r?\n.*` first.)
3. **File Read** action
   - **File Path:** `C:\Path\To\Your\MixItUpMagic8CardCommand\latest_card_path.txt`
   - **Save to:** a Special Identifier, e.g. `$cardpath`
4. **Overlay → Show Image**
   - **Image Path:** `$cardpath`
   - Configure entrance animation, duration, and position to taste.

### Setting up the command

1. Open Mix It Up
2. Go to **Commands** → **Chat Commands**
3. Create a new chat command:
   - **Name:** `!ask`
   - **Trigger:** `!ask`
4. Add the actions above for your chosen wiring option.

### How It Works

- `!ask will today be lucky` → draws a random card, writes a timestamped image, prunes old ones, prints verdict + path.
- `!ask` (no argument) → same behavior. The argument is flavor; the verdict comes from the card.

## Cleanup

Each run keeps the `KEEP_IMAGES` most recently modified `card-*.jpg` files in `IMAGE_OUTPUT_DIR` and deletes the rest. The default of 5 leaves enough headroom that the file currently being displayed by the overlay won't be deleted out from under it.

## Files

| File | Description |
|---|---|
| `ask_command.py` | CLI entry point |
| `scryfall_api.py` | Scryfall request + image download |
| `config.py` | Configuration and timing helpers |
| `ask.bat` | Windows batch wrapper for Mix It Up |
| `.env.example` | Template for optional configuration |
| `card-<timestamp>.jpg` | Auto-generated card images, pruned to the most recent N (not committed) |
| `latest_card_path.txt` | Auto-generated pointer to the newest card image (not committed) |

## Privacy Note

This tool makes anonymous requests to the public Scryfall API. No API keys or credentials are required or sent.

## License

MIT — see the parent repository for license details.
