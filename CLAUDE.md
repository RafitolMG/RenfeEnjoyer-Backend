# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A bot that automates booking seats on Renfe (Spanish railway) season passes ("abonos") with Selenium. The
user picks a saved profile, a direction and a date; the bot logs into `venta.renfe.com`, opens the pass,
lists that day's trains for the user to choose one, then refreshes the results page until the chosen train
has seats, reserves it, and hands the browser over so the user completes the booking by hand.

Despite the `-Backend` repo name there is no separate frontend repo — this is a **monorepo**:

- `backend/` — FastAPI app wrapping the Selenium bot, SQLite for profiles.
- `frontend/` — Vue 3 + TypeScript SPA (Vite) that launches searches and streams progress.

It was a Tkinter desktop app until the v2 restructure; that version lives on the `ubuntu-stable` branch.

## Running & building

```bash
# One-off setup on a machine: venv at the repo root (not backend/), npm ci, `renfe` link in ~/.local/bin.
# Reports missing system packages instead of installing them. Clone with -b ubuntu-dev: `main` is still
# the old Tkinter app.
./scripts/install.sh

# Development, two terminals
cd backend && ../.venv/bin/uvicorn app.main:app --reload   # http://127.0.0.1:8000
cd frontend && npm run dev                                 # http://localhost:5173
```

Vite proxies `/api` (HTTP **and** WebSocket) to port 8000, so the SPA is same-origin in dev and CORS only
matters for other setups.

`scripts/serve-tailscale.sh` (installed as the `renfe` command via a symlink in `~/.local/bin`) serves the
built SPA from FastAPI on a single port bound to the machine's Tailscale IP. It rebuilds the SPA when any
source is newer than `dist/index.html`, waits for `/api/health`, opens the MagicDNS URL in the browser when
run from a desktop session, and only opens the browser if the server is already up. It resolves its own path
through `readlink -f` so the symlink works, and traps signals so stopping it never orphans uvicorn. It
advertises the full MagicDNS name, not the IP (which changes when the node re-registers) nor the short name
(which on this machine resolves to its own IPv6 addresses, where the server does not listen). `app.main`
mounts `frontend/dist` at `/` only when that directory exists, after the API routers so the catch-all does
not shadow them; in dev the mount is simply absent.

```bash
cd backend  && ../.venv/bin/pytest -q            # single test: pytest tests/test_jobs_api.py::test_name
cd backend  && ../.venv/bin/ruff check . && ../.venv/bin/ruff format --check . && ../.venv/bin/mypy
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
- **The browser profile is persistent and per-account.** `driver.profile_dir_for()` keys it on a
  hash of the Renfe email under `config.PROFILE_DIR`, passed as `--user-data-dir`, so the usual path
  skips the login entirely and with it the captcha and the code. One shared profile would be a
  correctness bug, not just untidy: `_session_is_active` can only see that *a* session is open, not
  whose, so the bot would search on whichever account logged in last. `_ensure_session` loads
  the passes page and checks whether the URL still holds `myPassesCard.do`: unauthenticated, Renfe
  bounces to its public homepage rather than to the login form, so looking for a login field there
  would never match. Whether Renfe's auth cookie survives a browser restart is unverified — a
  session cookie would not, no matter the profile.
- **Whether a profile is logged in is recorded, never inferred.** The bot writes `SESSION_MARKER` into the
  profile when it sees the session work and removes it before logging in again; the SPA's indicator reads
  only that. The profile's contents prove nothing: Chrome fills the directory the moment it opens, and a
  search stalled on the captcha left 21 Renfe cookies behind with no login.
- **Renfe's login is behind reCAPTCHA.** Measured against the live site, an automated session
  scores badly enough to get an image challenge in both headless and headed runs, so the login
  cannot be fully unattended. The bot does not try to solve it: `awaiting_human` hands the window
  over and waits (`HUMAN_STEP_TIMEOUT`) until the challenge is gone, then carries on. A persistent
  Chrome profile would likely raise the score, but that is untested.
- **Three states park the worker on the user instead of failing**, all through the per-job `Interaction`
  bundle that `run_search` receives: `awaiting_code` waits on `interaction.code` until `POST
  /api/jobs/current/code` supplies the verification code; `awaiting_train` waits on `interaction.train`
  until `POST /api/jobs/current/train` picks a listed departure; `reserved` waits on
  `interaction.release`. All are cancellable. A `ValuePrompt` must be opened (`request()`) *before* its
  state is announced, or a client answering instantly is refused with `PromptNotOpen`.
- **The verification code goes through Renfe's two-step modal**, whose ids (`OTP_*` in `renfe.py`) come
  from markup captured on the live site. Validar is a `type="button"` with an `onclick`, so the bot clicks
  it: pressing Enter in the field sends nothing. After each code it waits for Renfe's verdict instead of
  re-prompting straight away; a rejection asks the user again, and running out of attempts clicks
  "Generar código" first. The error labels are hidden before each submit, because one left on screen by
  the previous code would read as the verdict on the next before Renfe has checked it. How the modal
  behaves after "Generar código" is unverified.
- **The job stream is the only source of truth for job state.** Action endpoints return a status,
  but the SPA deliberately ignores it: the worker usually announces the next state before the HTTP
  response lands, and applying the response afterwards rolled the UI back (measured: after choosing a
  train the picker stayed up while the bot was already polling, 3 runs of 3). Starting a job broadcasts
  a fresh `snapshot` so clients drop the previous job's log. `snapshot`, `trains` and `search` messages
  are broadcast without being recorded in the history, since the status they carry is already in any
  replayed snapshot.
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
  - `list_trains` reads the results table generically: every `td[data-label]` cell is passed through and
    the SPA builds its columns from them. Only the `Salida` label is relied on — it is the one the
    original code proved — so the other columns Renfe shows are **unverified**, as is whether the table
    lists the whole day at once. Trains sharing a departure time are listed once, because polling tells
    them apart by that time alone.
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
  fixture. Tests that exercise a job monkeypatch `app.bot.runner.run_search(request, reporter, interaction)`
  — never drive the real Renfe site.
- **Ruff flags `Depends()` in defaults (B008)**, so dependencies use the `SessionDep` alias in `app/api/deps.py`
  rather than `session: Session = Depends(get_session)`.

## Environment notes

- Developed on CachyOS (Arch) with Python 3.14 and Node 26; CI pins Python 3.12 / Node 22.
- `build_chrome_driver()` resolves the browser binary by name (`google-chrome`, `chromium`, …) because
  Selenium only looks for `google-chrome` by default, and falls back to Selenium Manager when no system
  `chromedriver` is on PATH. On Arch both come from the `chromium` and `chromedriver` packages.
- **The server may run outside the desktop session** — `serve-tailscale.sh` launched from a terminal, a
  service, SSH — and a visible browser then has no display and exits on launch (`SessionNotCreatedException:
  Chrome instance exited`). `driver.browser_environment()` points the browser at the user's Wayland socket in
  `XDG_RUNTIME_DIR` when neither `WAYLAND_DISPLAY` nor `DISPLAY` is set. Selenium's `Service(env=...)`
  *replaces* the process environment rather than extending it, so the whole mapping is passed. With no
  desktop session logged in at all there is nothing to open on; that surfaces as `BrowserUnavailable`.
- **Headless is opt-in** (`RENFE_HEADLESS=1`) and only useful for debugging: the user has to see the window
  to finish the purchase.
- System Python on Arch is PEP 668 externally-managed — always install into a venv.
- `vue-tsc` is incompatible with TypeScript 7 (it requires the `typescript/lib/tsc` subpath, which TS 7
  removed from its exports), so `typescript` is pinned to the 5.x line.
