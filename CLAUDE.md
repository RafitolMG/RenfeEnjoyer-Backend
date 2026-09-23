# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A bot that automates buying Renfe (Spanish railway) season-pass ("abono") tickets with Selenium. The user
picks a saved profile, a departure time, a direction and a date; the bot logs into `venta.renfe.com`, opens
the pass and refreshes the results page until a train at that time has seats, reserves it, and then hands the
browser over so the user completes the purchase by hand.

Despite the `-Backend` repo name there is no separate frontend repo — this is a **monorepo**:

- `backend/` — FastAPI app wrapping the Selenium bot, SQLite for profiles.
- `frontend/` — Vue 3 + TypeScript SPA (Vite) that launches searches and streams progress.

It was a Tkinter desktop app until the v2 restructure; that version lives on the `ubuntu-stable` branch.

## Running & building

```bash
# Backend
cd backend
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload          # http://127.0.0.1:8000

# Frontend
cd frontend
npm install && npm run dev                       # http://localhost:5173
```

Vite proxies `/api` (HTTP **and** WebSocket) to port 8000, so the SPA is same-origin in dev and CORS only
matters for other setups.

`scripts/serve-tailscale.sh` serves the built SPA from FastAPI on a single port bound to the machine's
Tailscale IP. `app.main` mounts `frontend/dist` at `/` only when that directory exists, after the API
routers so the catch-all does not shadow them; in dev the mount is simply absent.

```bash
cd backend  && .venv/bin/pytest -q               # single test: pytest tests/test_jobs_api.py::test_name
cd backend  && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy
cd frontend && npm run typecheck && npm run build
```

CI (`.github/workflows/ci.yml`) runs exactly these on push and PR.

## Architecture

A search is a **background job**, not a blocking call. That shape is the whole point of the v2 rewrite and
everything else follows from it:

1. `POST /api/jobs/current` validates the request, loads the profile's credentials and calls
   `JobManager.start()`.
2. `JobManager` (`app/bot/runner.py`) spawns one worker thread running `run_search` and returns immediately.
3. The bot reports through a `Reporter`; the manager stamps each event and hands it to the event loop with
   `loop.call_soon_threadsafe`, which fans it out to every WebSocket subscriber.
4. `GET /api/jobs/stream` (WebSocket) replays a snapshot on connect, so a client that joins late — or
   reconnects — still renders the full log.

Key invariants:

- **Only one job at a time.** Each job owns a visible browser window the user must interact with, so
  `start()` raises `JobConflict` (HTTP 409) while another is active.
- **Two states park the worker on an event instead of failing.** `awaiting_code` waits on a
  `CodePrompt` until `POST /api/jobs/current/code` supplies the verification code Renfe sent;
  `reserved` waits on `release`. Both are cancellable. The OTP field is matched by the heuristic
  selectors in `config.OTP_SELECTOR` — **unverified against the real markup**, since triggering it
  needs a live login with verification enabled. `RENFE_OTP_SELECTOR` overrides it, and a failed
  login logs the page's visible inputs so the real selector can be identified.
- **`reserved` is not a terminal state.** The worker parks on the `release` event until the user confirms
  via `POST /api/jobs/current/release`; only then is the browser closed. This replaces the old
  `input('Presiona Enter...')` that made the app console-only.
- **Cancellation is cooperative.** `cancel` is a `threading.Event` checked at each step, and every sleep goes
  through `_sleep()`, which waits on that event instead of `time.sleep`. Adding a bare `time.sleep` to the
  bot would make "Detener" hang for that long.

## Gotchas specific to this codebase

- **Renfe's DOM ids are hardcoded and brittle.** They live at the top of `app/bot/renfe.py`. Expect breakage
  whenever Renfe changes their markup; that file is where to look first.
  - The pass button's id is `new<abono>` right-padded with spaces, so it is matched with an XPath
    `starts-with`, not an exact id.
  - Results rows are `row<n>` and the matching reserve button is `continuar<n>` — the number is sliced off
    the row id.
  - `modalGeneric` being visible means the train filled up between listing and reserving: refresh, don't fail.
  - Clicks go through `_click`, which falls back to a scripted click. `element_to_be_clickable` only
    checks visible-and-enabled, not that the element is on top: measured against the live page, the
    OneTrust banner covers its own reject button and intercepts the native click in roughly 5 of 6 runs.
    In the pre-v2 code that exception was swallowed by a blanket `except Exception: print(e)`, so the bot
    died at the cookie banner and never reached the login form — the "it takes 5-10 tries" symptom.
  - `fill_field` reads the value back after typing and retries, because `send_keys` reports success even
    when the page swallows the keystrokes, which otherwise submits the login form empty.
- **`loginParticular.do` vs `loginCEX.do`**: only the former accepts an email in the `num_tarjeta` field.
  `loginCEX` is the company login and wants a client number.
- **The legacy DB has its columns semantically swapped.** The old `add_user(user, mail, ctr, abono)` wrote
  against `(username, password, email, abono)`, so `password` holds the email and vice versa.
  `scripts/migrate_legacy_db.py` un-swaps them on import. The current schema is correct — do not replicate
  the swap.
- **Credentials are stored in plaintext** in the local SQLite file. `UserRead` deliberately omits the
  password so it never reaches the client, and a blank password in `PATCH /api/users/{id}` means "keep the
  stored one". Encryption at rest is still an open task.
- **`JobManager` is a process-wide singleton**, so tests reset it through the autouse `reset_job_manager`
  fixture. Tests that exercise a job monkeypatch `app.bot.runner.run_search` — never drive the real Renfe site.
- **Ruff flags `Depends()` in defaults (B008)**, so dependencies use the `SessionDep` alias in `app/api/deps.py`
  rather than `session: Session = Depends(get_session)`.

## Environment notes

- Developed on CachyOS (Arch) with Python 3.14 and Node 26; CI pins Python 3.12 / Node 22.
- `build_chrome_driver()` resolves the browser binary by name (`google-chrome`, `chromium`, …) because
  Selenium only looks for `google-chrome` by default, and falls back to Selenium Manager when no system
  `chromedriver` is on PATH. On Arch both come from the `chromium` and `chromedriver` packages.
- **Headless is opt-in** (`RENFE_HEADLESS=1`) and only useful for debugging: the user has to see the window
  to finish the purchase.
- System Python on Arch is PEP 668 externally-managed — always install into a venv.
- `vue-tsc` is incompatible with TypeScript 7 (it requires the `typescript/lib/tsc` subpath, which TS 7
  removed from its exports), so `typescript` is pinned to the 5.x line.
