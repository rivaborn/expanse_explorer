# Expanse Explorer Project Rules (Svelte + Node.js)

Companion to the [Expanse](../expanse/) project. Reads a `.sqlite` exported from Expanse (`GET /download_db`), lets the user browse items by user/subreddit, and reassign items between users. Merges new uploads into its working DB rather than replacing it.

## Tech Stack
- **Frontend:** Svelte (located in `/frontend`)
- **Backend:** Node.js + Express (located in `/backend`)
- **Database:** SQLite via `better-sqlite3`, stored at `backend/data/current.sqlite`
- **Deployment:** Docker Compose, intended to run locally (no external network calls)

## Commands
- **Install All:** `cd frontend && npm install && cd ../backend && npm install`
- **Run Frontend (Dev):** `cd frontend && npm run dev`
- **Run Backend (Dev):** `cd backend && npm run dev`
- **Build All:** `./run.sh prod build`

## Data Flow
1. Expanse → `GET /download_db` → user downloads `.sqlite`
2. User uploads `.sqlite` to Explorer via `POST /open_db`
3. Explorer merges into `backend/data/current.sqlite` (add-only, preserves prior moves via the `moves` audit table)
4. User browses + moves items inside Explorer
5. Optional: `GET /download_db` to save the modified working DB locally

No data flows back to Expanse.

## Architecture Notes
- One Express server, no auth (local tool).
- SQLite schema mirrors Expanse's five tables (drops the Postgres-specific tsvector column), plus a `moves` audit table used by `/open_db` to avoid reverting user-initiated moves.
- The frontend is an SPA; double-clicking an item row opens its Reddit URL in a new tab.
