# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Companion to the [Expanse](../expanse/) project. Reads a `.sqlite` exported from Expanse (`GET /download_db`), lets the user browse items by user/subreddit, and reassign items between users. Merges new uploads into its working DB rather than replacing it.

## Tech Stack
- **Frontend:** SvelteKit (SSR disabled; static SPA) in `/frontend/source/`
- **Backend:** Node.js + Express (ESM) in `/backend/controller/server.mjs`
- **Database:** SQLite via `better-sqlite3`, stored at `backend/data/current.sqlite`
- **Deployment:** Docker Compose; intended to run locally (no external network calls)

## Commands

```bash
# Install
cd frontend && npm install && cd ../backend && npm install

# Dev (run both together)
cd frontend && npm run dev        # port 1400; proxies /backend → localhost:1401
cd backend && npm run dev         # port 1401; nodemon, hot-reload

# Production build & run
./run.sh prod build               # Docker image
./run.sh prod up [--watch]        # Start prod stack (backend only, static frontend)
./run.sh prod down
./run.sh prod update              # Pull, rebuild, restart

# Dev Docker stack
./run.sh dev build
./run.sh dev up                   # ports 1400 (frontend) + 1401 (backend)
```

There are no test suites and no lint scripts in either package.json.

## Data Flow

1. Expanse → `GET /download_db` → user downloads `.sqlite`
2. User uploads `.sqlite` to Explorer via `POST /open_db`
3. Explorer merges into `backend/data/current.sqlite` (add-only, preserves prior moves via the `moves` audit table)
4. User browses + moves items inside Explorer
5. Optional: `GET /download_db` to save the modified working DB locally

No data flows back to Expanse.

## Architecture

### Backend (`backend/controller/server.mjs`, `backend/model/db.mjs`)

Single Express server with these REST endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/open_db` | Upload & merge a `.sqlite` (multipart, up to 1 GiB) |
| GET | `/users` | All users sorted by item count |
| GET | `/subs?username=` | Subreddits for a user with item counts |
| GET | `/items?username=&sub=` | Items for a user/subreddit |
| POST | `/move` | Move items between users (atomic, writes `moves` audit row) |
| POST | `/set_read` | Mark an item read/unread |
| GET | `/download_db` | Download current SQLite file |

In dev mode (`RUN=dev`) CORS is open. In prod the built frontend is served as static files from the same Express process.

### Database Schema (`backend/model/db.mjs`)

WAL mode, foreign keys enabled. Key invariants: items are **never deleted**, only added; moves are **tracked** so a re-upload can't revert a user-initiated reassignment.

```
user_              (username PK, reddit_token, last_sync_epoch, …)
item               (id PK, type, content, author, sub, url, created_epoch)
user_item          (username, item_id, category, added_epoch, read_epoch — composite PK)
item_sub_icon_url  (sub PK, url)
item_fn_to_import  (id PK, fn_prefix)
moves              (item_id, from_username, from_category, to_username, to_category, moved_at_epoch)
```

`merge_from_file(path)` runs inside a transaction; it checks the `moves` table before assigning items so in-Explorer moves win over the uploaded file.

### Frontend (`frontend/source/routes/index.svelte`)

Single-route SPA with no component files—all UI lives in `index.svelte`. Styling is Bootstrap 4.6 dark theme loaded via CDN in `app.html`.

Key patterns:
- **Virtual scrolling:** only visible rows + a 10-row buffer are rendered. Row height is 36 px desktop / 56 px mobile. Update `ROW_HEIGHT` / `ROW_HEIGHT_MOBILE` constants if you change row sizing.
- **`read_overrides` map:** read state changes are applied locally first, then synced to `/set_read` in the background, so the UI stays responsive.
- **Backend URL:** `globals.js` sets `backend = ""` in prod (same origin) and `"/backend"` in dev (Vite proxy strips the prefix and forwards to port 1401).
- **Item selection & move:** checkboxes populate `selected_item_ids`; `apply_move()` POSTs to `/move` then reloads items.
- SSR is disabled in `hooks.js`; the static adapter in `svelte.config.js` outputs a fully client-side bundle.
