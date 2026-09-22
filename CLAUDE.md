# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Tkinter desktop app** (despite the `-Backend` repo name) that automates buying Renfe (Spanish railway)
season-pass ("abono") tickets via Selenium. The user picks a saved profile, enters a departure time / direction /
date, and the bot logs into `venta.renfe.com`, navigates to the pass, and polls the results page — refreshing until
a train at the requested departure time has seats, then reserves it and waits for the user to confirm.

Originally built for **Windows** (`.ico` icon, bundled `chromedriver.exe`, PyInstaller windowed `.exe`); it has
since been ported to run on Linux — see "Cross-platform" below.

## Running & building

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # first-time setup
.venv/bin/python main.py                                            # launch the GUI
```

- Entry point is `main.py` → `src/templates/index.py:main()`.
- **Always run from the repo root.** There are no `__init__.py` files anywhere — the `src.*` imports rely on PEP 420
  namespace packages resolving against the CWD, and the SQLite file is opened by the bare relative name
  `renfe_enjoyer_database.db`, so running from elsewhere both breaks imports and silently creates a second empty DB.
- On a fresh checkout the DB does not exist (it is gitignored). Run **Datos → Create Database** once before adding users.
- Only dependency is `selenium` (`requirements.txt`); `tkinter` and `sqlite3` are stdlib but `tkinter` needs the
  system Tk package.
- **PyInstaller `RenfeEnjoyer.spec` is stale**: it references `RenfeEnjoyer.py`, which does not exist. The real
  entry is `main.py` — update the spec's `Analysis([...])` before building an executable.
- No test suite, linter, or CI is configured.

## Architecture

Flow: `main.py` → `index.py` (builds the main window + "Datos" menu) → user actions call into
`src/data/database.py` (persistence) and `src/core.py` (the Selenium bot).

- **`src/core.py`** — the automation. `renfe_enjoyer(hora_de_salida, ida_vuelta, fecha_input, mail, ctr, abono)`
  drives a single Chrome session: login → open the pass (`abono` is used to build the DOM id `new{abono}` padded
  with trailing spaces) → select `ida`/`vuelta` → set the date → **infinite `while True` refresh loop** matching a
  table row by `data-label='Salida'` text against `hora_de_salida`, then clicking the derived `continuar{n}` button.
  `build_chrome_driver()` resolves the browser/driver binaries across platforms (see below). Renfe DOM ids are
  hardcoded and brittle — expect breakage when Renfe changes their markup.
- **`src/data/database.py`** — SQLite (`renfe_enjoyer_database.db`, created in the CWD). Each function opens/closes
  its own connection and reports outcomes via `modals.show_success/show_error`.
- **`src/templates/`** — all Tkinter UI. `index.py` is the main window; `auth/register_user.py` and
  `views/user_selection.py` are `Toplevel` dialogs; `modals/modals.py` wraps `messagebox`; `ui_utils.py` holds the
  cross-platform icon helper.

## Gotchas specific to this codebase

- **`create_database()` destroys data**: it runs `DROP TABLE IF EXISTS users` every time, so the "Create Database"
  menu item wipes all saved users. It must be run once on first setup, never again.
- **The DB columns are semantically swapped vs. their names.** `add_user(username, password, email, abono)` is
  called from `register_user.py` as `add_user(user, mail, ctr, abono)`, so the `password` column actually stores the
  email and the `email` column stores the password. `index.py` compensates by reading `get_user(...)[2]` as the
  login mail and `[3]` as the login password when calling `renfe_enjoyer`; `user_selection.py:on_edit` does the same
  when pre-filling the edit form. The double-swap cancels out and it works, but **do not "fix" one side without the
  others.** Row layout is `(id, username, password, email, abono)`.
- **`edit_user()` cannot rename a user.** Its SQL is `UPDATE users SET username=?, ... WHERE username=?` with the
  *new* username bound to both, so changing the username in the edit dialog matches no row and silently saves nothing.
- **The bot freezes the GUI.** `renfe_enjoyer` runs synchronously on the Tk main thread from the "Buscar billetes"
  button, so the window is unresponsive for the entire (potentially unbounded) polling loop, and it ends with a
  blocking `input('Presiona Enter...')` on stdin — the app is only usable when launched from a console. The whole
  function is wrapped in `except Exception: print(e)`, so failures never surface in the UI.
- **No user selected → `TypeError` on stdout, no modal.** `index.py` calls `current_user_data()[2]` directly; when
  nothing is selected `get_user` returns `None`. It also re-queries the DB three times per click.
- **Renfe login URL matters**: `loginParticular.do` accepts an email in the `num_tarjeta` field (labelled
  "Email / Número Más Renfe"). `loginCEX.do` is the *company* login and takes a client number, not an email.
- **`get_all_users()` returns rows, not strings** — `user_selection.py` assigns those 1-tuples straight to
  `Combobox['values']`, which works only because Tcl flattens `('Dani',)` to `Dani`. A username containing a space
  would come back from `.get()` brace-wrapped and fail the lookup.
- **`src/templates/auth/edit_user.py` is dead code** — it defines its own `registro()` but is imported nowhere. The
  live edit flow is inlined in `views/user_selection.py:on_edit`.
- **`src/templates/tkStyles/tkStyles.py`** is a scratch file that just prints `ttk` theme names on import — not used.
- `index.py` still has a leftover `test` button wired to `current_user_data()`.

## Cross-platform

The app was written for Windows and is now also run on CachyOS (Arch-based). Both platform seams are already
abstracted — keep new code going through them rather than reintroducing Windows-only calls:

- **Browser/driver** — `src/core.py:build_chrome_driver()` probes `PATH` for `google-chrome`,
  `google-chrome-stable`, `chromium`, `chromium-browser` and sets `Options.binary_location`, then uses a system
  `chromedriver` if present and otherwise falls back to Selenium Manager. On Arch these come from the `chromium`
  and `chromedriver` pacman packages at `/usr/bin/`. The committed `chromedriver.exe` is the Windows leftover and is
  not used on Linux.
- **Window icon** — `wm_iconbitmap()` on a `.ico` raises `TclError` on Linux, which used to crash every window.
  All windows now call `src/templates/ui_utils.py:set_window_icon()`, which resolves `assets/u327as.ico` relative to
  the source file (not the CWD) and swallows the `TclError`.
- System Python on Arch is **PEP 668 externally-managed** — install into the project venv, never system-wide.
  `tkinter` needs `sudo pacman -S tk`.
