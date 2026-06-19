# Mix It Up MTG Trivia Game

A continuously-running Magic: The Gathering trivia game designed for a Twitch BRB (Be Right Back) scene. While you're away, viewers see a question + four multiple-choice answers on screen, vote in chat with `!vote A` (or B, C, D), and after a timer the correct answer is revealed with the vote tally. Then the next question loads. The loop runs until you stop it.

- Questions you write yourself in a single JSON file.
- Optional Scryfall card images on the question prompt and on any of the four answers (look up by card name).
- Difficulty badges: Easy / Medium / Difficult.
- Vote tallies update live; the correct answer is revealed when the timer hits zero.
- Drop in your own background graphic — it's just `static/background.png`.

## How it works

This tool runs a small local web server (Flask) at `http://localhost:8765`. You point an **OBS Browser Source** at it; that browser source becomes your BRB screen. Mix It Up forwards chat votes to the server via its built-in Web Request action. Everything stays on your machine.

## Features

- Continuous question loop while you're BRB — no manual triggering between questions
- Live vote tallying per round (one vote per viewer; first vote locks in — no changing answers)
- Two leaderboards — a per-session board (resets each run) and a persistent all-time board (survives restarts). The overlay shows one at a time and rotates between them. Correct answers earn points weighted by difficulty
- Smooth countdown timer rendered locally for no jitter
- Bot username denylist (`nightbot`, `streamelements`, `streamlabs`, `moobot` by default)
- Scryfall card images prefetched at startup and cached for 30 days
- Question images for prompts like "which card is this?", with selective censoring (hide name, mana cost, art, etc.)
- Graceful degradation when Scryfall is unreachable (text-only fallback)
- Optional mod-only skip + scoreboard-reset endpoints
- Optional `DEBUG_TIMING` flag prints per-step timing to stderr

## Setup Instructions

### 1. Install Python

Download and install Python 3.8+ from [python.org](https://www.python.org/downloads/) and check **Add Python to PATH** during install.

> **Watch out for the Microsoft Store stub.** On a fresh Windows machine without real Python installed, typing `python` opens the Microsoft Store instead of running anything. If you see `Python was not found; run without arguments to install from the Microsoft Store...`, finish the python.org install above, then go to **Settings -> Apps -> Advanced app settings -> App execution aliases** and turn off both `python.exe` and `python3.exe` entries. `trivia.bat` prefers the `py` launcher (bundled with the python.org installer) so it sidesteps this stub once Python is actually installed.

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

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8765` | Port the server listens on. Change if 8765 is in use. |
| `ASK_SECONDS` | `30` | Seconds viewers have to vote on each question. |
| `REVEAL_SECONDS` | `8` | Seconds the correct answer is shown before the next question. |
| `QUESTIONS_FILE` | `./questions.json` | Path to the trivia questions file. |
| `BOT_USERNAMES` | `nightbot,streamelements,streamlabs,moobot` | Comma-separated usernames whose votes are ignored. |
| `SKIP_SECRET` | (empty) | If set, the `/skip` and `/reset` endpoints require this value in an `X-Skip-Secret` header. |
| `SHOW_SCOREBOARD` | `true` | Set to `false` to hide the on-screen leaderboard. |
| `SCOREBOARD_SIZE` | `5` | How many top players to list in each leaderboard section. |
| `SCOREBOARD_ROTATE_SECONDS` | `6` | How often the leaderboard rotates between This Session and All-Time. |
| `SCORES_FILE` | `./scores.json` | Where the all-time leaderboard is stored. Delete this file to wipe all-time standings. |
| `POINTS_EASY` | `1` | Points awarded for a correct answer on an Easy question. |
| `POINTS_MEDIUM` | `2` | Points awarded for a correct answer on a Medium question. |
| `POINTS_DIFFICULT` | `3` | Points awarded for a correct answer on a Difficult question. |
| `EDITOR_PORT` | `8766` | Port for the question editor (`editor.bat`). Localhost only. |
| `OPEN_BROWSER` | `true` | When true, `editor.bat` opens your browser to the editor on startup. |
| `DEBUG_TIMING` | `false` | Set to `true` to print per-step timing to stderr. |

### 4. Write your trivia questions

Edit `questions.json`. A sample file is included covering Easy, Medium, and Difficult questions, including a couple with card images on the question prompt.

The schema:

```json
{
  "version": 1,
  "questions": [
    {
      "id": "q-001",
      "difficulty": "Easy",
      "question": "Which color is most associated with creature destruction?",
      "question_image": null,
      "options": [
        { "text": "White", "card": null },
        { "text": "Black", "card": null },
        { "text": "Blue",  "card": null },
        { "text": "Green", "card": null }
      ],
      "correct": 1,
      "explanation": "Black has the largest share of unconditional removal."
    },
    {
      "id": "q-002",
      "difficulty": "Medium",
      "question": "What is this card's mana cost?",
      "question_image": {
        "card": "Lightning Bolt",
        "alt_text": "A red instant",
        "hide": ["name", "mana_cost"]
      },
      "options": [
        { "text": "R",  "card": null },
        { "text": "1R", "card": null },
        { "text": "2R", "card": null },
        { "text": "RR", "card": null }
      ],
      "correct": 0,
      "explanation": "Lightning Bolt costs R — one red mana, three damage to any target."
    }
  ]
}
```

Rules:

- `version` must be `1`.
- `id` is optional; if omitted, it's auto-generated as `q-NNN`.
- `difficulty` controls the badge color: `Easy` -> green, `Medium` -> yellow, `Difficult` -> red. Other strings render as a gray badge.
- `question` is required.
- `question_image` is `null`, or `{ "card": "<Scryfall name>", "set": "<optional set code>", "alt_text": "<optional>", "hide": ["..."] }`. The card image appears next to the question. Use `hide` to censor parts of the card so viewers have to guess what's underneath (see below). Use `set` to pin the printing (see "Pinning a specific printing" below).
- `options` must contain exactly 4 entries. Each has `text` (required), `card` (Scryfall card name, or `null` for text-only), and optional `set` and `hide`.
- `correct` is the 0-based index (0, 1, 2, or 3) of the right answer.
- `explanation` is optional text shown below the correct answer during the reveal.

#### Hiding parts of a card

The `hide` field accepts a list of named regions. Two flavors:

**Card-image regions** — sage-green block over that part of the card image.

| Region | Covers |
|---|---|
| `name` | Title bar at the top |
| `mana_cost` | Mana cost in the top-right corner |
| `art` | The artwork |
| `type` | Type line between art and rules text |
| `text` | Rules / flavor text box |
| `pt` | Power/Toughness in the bottom-right (creatures only) |
| `artist` | Artist credit at the bottom |
| `set` | Set / expansion symbol on the type line |
| `collector` | Bottom-left collector line (set/number/rarity letter) |

**Info chips** — render a small chip above the card. During ASK the chip shows `?`; during REVEAL the real value is shown.

| Region | Shows on reveal |
|---|---|
| `rarity` | Common / Uncommon / Rare / Mythic Rare (from Scryfall) |
| `price` | Scryfall USD market price (e.g. `$0.25`) |

> **Asking about rarity?** A modern card prints its rarity in two places — the set-symbol colour and the bottom-left collector line (the `U` / `R` / `M` letter). So hiding `rarity` **automatically** also covers the `set` symbol and the `collector` line on the card image, so the answer isn't sitting in plain sight. You don't need to list those yourself.
>
> **General rule:** if a question asks about something printed on the card (mana cost, type, rarity…), add that region to `hide` — otherwise the card shows the answer.

Example — ask for the mana cost while hiding both the name and the mana cost itself:

```json
"question_image": {
  "card": "Lightning Bolt",
  "hide": ["name", "mana_cost"]
}
```

Example — ask for rarity and price together:

```json
"question_image": {
  "card": "Black Lotus",
  "hide": ["rarity", "price"]
}
```

When the timer ends and the round transitions to REVEAL, **all censors and chip placeholders are lifted automatically** — viewers see the full card with the real rarity and price.

The card-region rectangles are tuned for the modern Magic frame (M15 / 2015 onward), which is what Scryfall returns for nearly all reprints. Old-frame (Alpha-era) cards may have the censor block slightly offset. Prices come from Scryfall and are cached for 30 days, so the displayed value may lag the live market by a few weeks.

#### Pinning a specific printing

By default, Scryfall picks whichever printing it ranks highest for the card name — that's often a recent reprint, not the canonical version. To force a specific printing, add a `set` field with the Scryfall set code:

```json
"question_image": {
  "card": "Black Lotus",
  "set": "lea"
}
```

| Set code examples | Set |
|---|---|
| `lea` | Limited Edition Alpha |
| `leb` | Limited Edition Beta |
| `2ed` | Unlimited |
| `4ed` | Fourth Edition |
| `mmq` | Mercadian Masques |
| `m15` | Magic 2015 (first modern frame) |
| `2x2` | Double Masters 2022 |
| `lci` | Lost Caverns of Ixalan |

Browse all set codes at [scryfall.com/sets](https://scryfall.com/sets). The `set` field is case-insensitive and works on both `question_image` and individual option entries.

Pinning a printing affects: the card image shown, the rarity chip (different sets often print the same card at different rarities), and the price (different printings have different market prices). It does **not** change the card's gameplay rules, mana cost, or text — those are universal.

To pin **one exact printing** — a specific collector number, art, or **language** (e.g. the Japanese version of a card) — a `question_image`/option can also carry a `print_id` (a Scryfall card id). The visual editor's Printing dropdown sets this for you; the `set` field alone can only target an English printing of a set.

The server validates the file at startup and refuses to start with a clear error if anything is wrong.

### 5. Edit questions & manage lists with the visual editor (optional)

Editing `questions.json` by hand is fiddly. A small **local editor** lets you add, edit, reorder, and delete questions through a form — with live Scryfall card previews and a **printing picker** (pick the exact printing from a dropdown instead of typing set codes — including specific collector numbers and **foreign-language cards**, e.g. "Secrets of Strixhaven Mystical Archive · #156 · JA"). The chosen printing is pinned by its Scryfall id, so the exact card you picked is what shows.

1. Double-click **`editor.bat`**. A console window opens and your browser opens to the editor automatically (set `OPEN_BROWSER=false` in `.env` to disable, then open **`http://localhost:8766/`** yourself).
3. Pick a question on the left (or **➕ Add**); fill in the form on the right — difficulty, question text, the four answers (mark the correct one), optional card images on the question and/or answers, what to hide, and an explanation.
4. Click **💾 Save changes**. The list is validated *before* writing — if something's wrong (e.g. a missing answer or no correct option), you get a precise error and nothing is overwritten.
5. Click **📢 Publish** (see below) and then **start/restart the trivia server** (`trivia.bat`) to load it.

The editor binds to `localhost` only (it writes files, so it stays off your network) and runs independently of the trivia server. Change its port with `EDITOR_PORT` in `.env`.

#### Multiple question lists

You can keep several named lists (e.g. *default*, *Commander Night*, *Halloween Special*) and switch between them. The bar at the top of the editor manages them:

- **List dropdown** — choose which list you're editing. The one marked **★ live** is the one the trivia server currently uses.
- **📢 Publish (make live)** — copies the selected list into `questions.json`, so it becomes the list the trivia server loads. **Editing a list does *not* change what's live** until you publish — so you can prep next week's list while the current one stays on stream.
- **➕ New** — create a list (blank, or a copy of the current one). **✎ Rename** / **🗑 Delete list** manage the rest. List names are unique.

**How it's stored.** Each list is a *master file* in `lists/<name>.json` with its own timestamp. `questions.json` is the **active mirror** — whatever list is currently published. On editor start-up the active list is reconciled with `questions.json`: if you edited `questions.json` directly (outside the editor) it's imported into that list, but a newer master (edited in the editor) is never overwritten, and nothing is auto-published. To wipe a list entirely, delete its file in `lists/`.

Switching/publishing a list takes effect when you next **(re)start the trivia server** — same as edits.

### 6. Add your background graphic (optional)

Drop a PNG named `background.png` into `static/`. It will be used as the full-screen background of the trivia overlay. If the file is missing, a dark purple/blue gradient is used as a fallback.

### 7. Run the server

Double-click `trivia.bat`. A console window opens and stays open while the loop runs. You should see:

```
[trivia] loading questions from ...questions.json
[trivia] loaded 8 questions
[trivia] prewarming 7 Scryfall card images...
[trivia] prewarmed 7/7 card images
[trivia] serving overlay at http://localhost:8765/overlay
[trivia] vote endpoint: http://localhost:8765/vote?user=<name>&choice=A
[trivia] close this window or Ctrl+C to stop
```

Open `http://localhost:8765/overlay` in a regular browser to confirm it renders. To stop the server, close the console window or hit Ctrl+C.

## OBS Setup

1. In OBS, add a **Browser Source** to your BRB scene.
2. Set the URL to `http://localhost:8765/overlay`.
3. Width: `1920`, Height: `1080` (or match your canvas).
4. Make sure **Shutdown source when not visible** is **off** — otherwise OBS reloads the page on every scene switch and viewers see "Loading..." for a moment.

## Mix It Up Integration

The viewers' votes are forwarded to this tool by Mix It Up's **Web Request** action.

### Wiring `!vote`

1. Open Mix It Up -> **Commands** -> **Chat Commands** -> create a command:
   - **Name:** `Trivia Vote`
   - **Trigger:** `!vote`
   - **Require argument:** Yes (or just set "Arguments Required" to 1)
2. Add a **Web Request** action:
   - **Method:** `GET`
   - **URL:** `http://localhost:8765/vote?user=$username&choice=$arg1text&display=$userdisplayname`
   - Leave the response handling empty — the server returns 200 OK with no body, and we don't want a chat reply (counts update on the overlay).
3. **No Chat action.** A chat reply on every vote would spam.

That's it. Viewers type `!vote A` (or B, C, D, case-insensitive). The overlay tally bar updates within half a second.

The `&display=$userdisplayname` part is what makes the leaderboard show nicely-cased names (e.g. `ResetwithTori` instead of `resetwithtori`). It's optional — if you leave it off, the scoreboard falls back to the lowercase login name.

### Scoreboard

Every correct answer earns points, weighted by question difficulty (Easy = 1, Medium = 2, Difficult = 3 by default — tune with `POINTS_*` in `.env`). The leaderboard on the right of the overlay shows **one board at a time and rotates** between two boards every `SCOREBOARD_ROTATE_SECONDS` (default 6s). Whoever just scored gets a little `+N` pop during the reveal:

- **This Session** — resets every time you start the server. This is the "who's winning right now" board for the current stream.
- **All-Time** — persists across restarts. Saved to `scores.json` (next to the script). It keeps growing until you clear it.

Early on, when only one board has any points, the overlay parks on that one and only starts alternating once both have entries.

Clearing the standings:

- **Restart the server** → the This-Session board resets; All-Time is untouched.
- **`!trivia_reset`** (mod command below) → resets This-Session by default.
- **Wipe All-Time** → delete `scores.json`, or use `!trivia_reset` with `?scope=total`. Deleting the file is the simplest way to start the all-time competition fresh.

Set `SHOW_SCOREBOARD=false` to hide both boards entirely.

### Optional: `!trivia_skip` for mods

If a question is broken or you want to move on, you can skip the current phase via HTTP. To wire it up:

1. Create a Mix It Up Chat Command with trigger `!trivia_skip`, restricted to **Moderators and Above**.
2. Add a **Web Request** action:
   - **Method:** `POST`
   - **URL:** `http://localhost:8765/skip`
   - If you set `SKIP_SECRET` in `.env`, also add a header `X-Skip-Secret: <your secret>`.

Skipping during ASK jumps to REVEAL immediately. Skipping during REVEAL jumps to the next question.

### Optional: `!trivia_reset` for mods

To clear a leaderboard mid-stream (e.g. starting a fresh competition), wire a mod-only command the same way:

1. Create a Mix It Up Chat Command with trigger `!trivia_reset`, restricted to **Moderators and Above**.
2. Add a **Web Request** action:
   - **Method:** `POST`
   - **URL:** `http://localhost:8765/reset` (add `?scope=total` to clear All-Time, or `?scope=all` to clear both)
   - If you set `SKIP_SECRET` in `.env`, also add a header `X-Skip-Secret: <your secret>` (the same secret gates both skip and reset).

The board clears within half a second. `scope` defaults to `session`. To wipe the All-Time board without a command, just delete `scores.json` and restart.

## Why a local web server (instead of the `{LocalFile:...}` overlay pattern)

The sibling `MixItUpMagic8CardCommand` writes a timestamped JPG and lets a Mix It Up HTML Overlay action display it via `{LocalFile:\\$path}`. That works great for a one-shot draw, but a trivia round has live state: an accumulating vote tally, a ticking countdown, and a phase transition from ASK to REVEAL. None of that maps cleanly to Mix It Up's overlay token.

Running a tiny local Flask server side-steps all of it: the overlay is just a static page that polls `/state` every 500ms, which is trivially debuggable (you can hit `/state` in any browser to see exactly what the overlay sees). And `/vote` gives Mix It Up a clean endpoint to forward chat votes to.

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Console says `Python is not installed on this machine.` | Neither `py` nor `python` resolves to a real Python. Install Python from [python.org](https://www.python.org/downloads/) (check **Add Python to PATH**) and, if needed, disable the App execution aliases for `python.exe` / `python3.exe` in Windows Settings. |
| Console shows `Address already in use` / `OSError: [WinError 10048]` | Port 8765 is occupied (maybe a previous run didn't shut down). Either kill the leftover Python process in Task Manager, or set `PORT=8766` in `.env`. |
| Overlay shows "Loading trivia..." and never advances | The browser can't reach the server. Confirm the server console is still running and that the URL is `http://localhost:8765/overlay`. If OBS uses `127.0.0.1` instead of `localhost`, that's fine too. |
| Votes from chat don't update the overlay | Open the Mix It Up command and confirm the Web Request URL is exactly `http://localhost:8765/vote?user=$username&choice=$arg1text`. Test by visiting that URL in a browser with your name and `choice=A` substituted — the tally should change. If it doesn't, check that the bot username isn't on the denylist. |
| One option has no card image but others do | Scryfall couldn't resolve that card name at startup. Check the console for `[scryfall] lookup failed for '<name>'`. Fix the name in `questions.json` (Scryfall's `?fuzzy=` is forgiving, but typos still bite) and restart. |
| Background graphic doesn't show | Confirm the file is at `static/background.png` (exact filename). Refresh the OBS Browser Source (right-click -> Refresh). Hard-refresh the page in a regular browser to confirm the file is reachable at `http://localhost:8765/static/background.png`. |
| Console refuses to start with a `questions.json` error | The validator caught a schema problem. The error message names the exact path (e.g. `questions[2].options[3].card`). Fix and restart. |
| Viewers say their `!vote` fired but their answer didn't count | They voted before the question started or after the timer expired. Votes outside the ASK phase are silently dropped — that's the design. |
| OBS Browser Source goes blank after a scene change | Turn off "Shutdown source when not visible" on the Browser Source properties — otherwise OBS reloads the page every time you switch back to BRB. |

## Files

| File | Description |
|---|---|
| `trivia_server.py` | Flask app + entry point |
| `game_loop.py` | Background thread driving phase transitions |
| `game_state.py` | Thread-safe state container |
| `questions.py` | Loads, validates, and saves `questions.json`; shuffle bag iterator |
| `scryfall_api.py` | Scryfall lookups (by name), printings list, image download + caching |
| `cache.py` | File-based JSON cache (Scryfall image URLs, 30-day TTL) |
| `config.py` | Environment loading + timing helper |
| `questions.json` | The trivia content — edit by hand or via the visual editor |
| `trivia.bat` | Windows entry point that prefers the `py` launcher |
| `editor_server.py` | Localhost-only question editor (CRUD API + UI) |
| `library.py` | Named question lists store (masters + active mirror + sync) |
| `editor.bat` | Windows entry point for the question editor |
| `lists/` | Named question lists (one master file each) — not committed |
| `static/overlay.html` | The page OBS Browser Source points at |
| `static/style.css` | Overlay styling and difficulty badge colors |
| `static/overlay.js` | Polls `/state` and renders the overlay |
| `static/editor.html` / `editor.css` / `editor.js` | The question editor UI |
| `questions.json.bak` | Auto-written backup on each editor save — not committed |
| `static/background.png` | (Optional) Your custom background graphic — not committed |
| `static/cards/` | Auto-populated Scryfall card images — not committed |
| `.env.example` | Template for optional configuration |
| `.cache.json` | Auto-generated Scryfall response cache — not committed |
| `scores.json` | All-time leaderboard — auto-generated, not committed. Delete to wipe all-time standings |

## Privacy Note

This tool makes anonymous requests to the public Scryfall API. No API keys or credentials are required. The local web server binds to `0.0.0.0:8765` so you can point a phone or tablet at it for testing on your LAN; if you'd rather restrict it to your own machine, change `host="0.0.0.0"` to `host="127.0.0.1"` in `trivia_server.py`.

## License

MIT — see the parent repository for license details.
