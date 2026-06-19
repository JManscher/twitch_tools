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

A single line on stdout — safe to drop straight into a Mix It Up Chat action:

```
The cards say IT IS CERTAIN: Lightning Bolt
```

Alongside it, the script overwrites `latest_card_path.txt` (next to the script, or in `IMAGE_OUTPUT_DIR`) with the absolute native path to the newest card image (e.g. `C:\...\card-1737654321123.jpg`). Mix It Up's File Read action reads this into a special identifier so the HTML Overlay can reference it.

On failure:

```
The cards are silent (random card request failed: ...).
```

## Setup Instructions

### 1. Install Python

Download and install Python 3.8+ from [python.org](https://www.python.org/downloads/) and check **Add Python to PATH** during install.

> **Watch out for the Microsoft Store stub.** On a fresh Windows machine without real Python installed, typing `python` opens the Microsoft Store instead of running anything. If you see `Python was not found; run without arguments to install from the Microsoft Store...`, finish the python.org install above, then go to **Settings → Apps → Advanced app settings → App execution aliases** and turn off both `python.exe` and `python3.exe` entries. `ask.bat` prefers the `py` launcher (bundled with the python.org installer) so it sidesteps this stub once Python is actually installed.

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

Mix It Up's overlay is an embedded browser that caches resources by URL. If we re-wrote the same `latest_card.jpg` every time, the overlay would often keep showing the previous card. Writing `card-<timestamp>.jpg` instead gives every draw a unique URL and forces the overlay to redraw.

### How Mix It Up loads local files in an overlay

For browser security reasons the overlay **cannot load local file paths directly** — neither as raw paths nor as `file:///` URLs. Mix It Up provides a dedicated token instead. Per the [Mix It Up Wiki](https://wiki.mixitupapp.com/en/services/overlay), the exact required syntax is:

```
{LocalFile:\\C:\Path\To\Your\Image.png}
```

Note the **literal `\\` prefix before the drive letter** — that's a Mix It Up convention, not an HTML escape. Omitting it produces a broken-image icon in the overlay even when everything else is wired correctly.

The token composes with `$identifier` substitution: Mix It Up expands `$cardpath` first, then translates the whole `{LocalFile:...}` token to a fetchable URL. So in your HTML body you write `{LocalFile:\\$cardpath}` and at runtime Mix It Up sees `{LocalFile:\\C:\...\card-1737654321123.jpg}` which is the form the wiki documents.

### Wiring the `!ask` command

1. Open Mix It Up → **Commands** → **Chat Commands** → create a command named `!ask` with trigger `!ask`.
2. Add an **External Program** action:
   - **File Path:** `C:\Path\To\Your\MixItUpMagic8CardCommand\ask.bat`
   - **Arguments:** `$arg1text`
   - **Wait for finish:** Yes
   - **Show window:** No
3. Add a **File Read** action:
   - **File Path:** `C:\Path\To\Your\MixItUpMagic8CardCommand\latest_card_path.txt`
   - **Save to Special Identifier:** `cardpath`
4. Add a **Chat** action:
   - **Message:** `$externalprogramresult`
   - The script's stdout is a single line (verdict + card name), so this drops straight into chat with no parsing needed.
5. Add an **Overlay → HTML** action:
   - **Reference Name:** anything unique, e.g. `cardpopup` (this is the field Mix It Up requires before letting you save — it's how later actions can target or remove this overlay item).
   - **HTML** (paste as a single line — Mix It Up's HTML field breaks tags at line breaks, so anything spanning multiple lines inside the tag will render as visible text instead of attributes):
     ```html
     <img src="{LocalFile:\\$cardpath}" style="max-width:400px;max-height:560px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,0.5);" />
     ```
   - Configure entrance/exit animations, duration, and position on the action to taste — these are Overlay-action settings, not HTML.

That's the full wiring. The Overlay → **Show Image** action is the wrong tool here: its path field doesn't substitute identifiers, and overlays can't load local paths without the `{LocalFile:...}` token anyway. Stick with **Overlay → HTML**.

### How It Works

- `!ask will today be lucky` → draws a random card, writes a timestamped image, prunes old ones, prints verdict + path.
- `!ask` (no argument) → same behavior. The argument is flavor; the verdict comes from the card.

## Cleanup

Each run keeps the `KEEP_IMAGES` most recently modified `card-*.jpg` files in `IMAGE_OUTPUT_DIR` and deletes the rest. The default of 5 leaves enough headroom that the file currently being displayed by the overlay won't be deleted out from under it.

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Chat says `The cards are silent (Python is not installed on this machine).` | Neither `py` nor `python` resolves to a real Python install. Install Python from [python.org](https://www.python.org/downloads/) (check **Add Python to PATH**) and, if needed, disable the App execution aliases for `python.exe` / `python3.exe` in Windows Settings. |
| Running `.\ask.bat` opens the Microsoft Store | Same as above — Windows is routing `python` to its Store stub. Install Python and disable the alias. |
| Chat says `The cards are silent (random card request failed: ...)` | Network reached, Scryfall didn't. Usually transient — retry. Persistent failures mean the host is offline or DNS to `api.scryfall.com` is blocked. |
| HTML Overlay action won't save / asks for a reference | The **Reference Name** field is required — type anything unique (e.g. `cardpopup`). It's the handle Mix It Up uses to identify this overlay item in later actions, not an image source. |
| HTML Overlay shows a broken-image icon | Likely causes, in order: (a) you wrote `{LocalFile:$cardpath}` instead of `{LocalFile:\\$cardpath}` — the wiki requires the literal `\\` prefix before the drive letter; (b) you used `$cardpath` raw or as `file:///...` without `{LocalFile:...}` at all — the overlay's browser can't load local paths without that token; (c) the File Read action runs *after* the Overlay action, so `$cardpath` is empty when the HTML renders — reorder so File Read precedes the Overlay action. |
| Overlay shows tiny broken-image icon AND visible text like `style="max-width: 400px..."` | Your `<img>` tag was pasted across multiple lines and Mix It Up's HTML field broke it at the newline, so the `style` attribute is now sitting outside the tag. Re-paste the snippet as a single line. |
| Chat message looks fine but the overlay shows an old card | The overlay is caching the previous URL. Make sure your `<img>` uses `{LocalFile:\\$cardpath}` — `$cardpath` is the timestamped filename and changes on every run, so the URL Mix It Up generates is also unique each time. If the chat line cites a new card name but the overlay doesn't change, your File Read is reading a stale path — confirm the action order. |

## Files

| File | Description |
|---|---|
| `ask_command.py` | CLI entry point |
| `scryfall_api.py` | Scryfall request + image download |
| `config.py` | Configuration and timing helpers |
| `ask.bat` | Windows batch wrapper for Mix It Up |
| `.env.example` | Template for optional configuration |
| `card-<timestamp>.jpg` | Auto-generated card images, pruned to the most recent N (not committed) |
| `latest_card_path.txt` | Auto-generated pointer to the newest card image, read by Mix It Up's File Read action (not committed) |

## Privacy Note

This tool makes anonymous requests to the public Scryfall API. No API keys or credentials are required or sent.

## License

MIT — see the parent repository for license details.
