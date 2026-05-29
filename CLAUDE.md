# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Companion to the [Expanse](../expanse/) project. Reads a `.sqlite` exported from Expanse (`GET /download_db`), lets the user browse items by user/subreddit **or** by topical category, reassign items between users, and categorize subreddits into persistent topical groupings. Merges new uploads into its working DB rather than replacing it.

## Tech Stack
- **Frontend:** SvelteKit (SSR disabled; static SPA) in `/frontend/source/`. SvelteKit 1.0.0-next.405, Svelte 3.49.
- **Backend:** Node.js + Express (ESM) in `/backend/controller/server.mjs`
- **Database:** SQLite via `better-sqlite3`, stored at `backend/data/current.sqlite`
- **Deployment:** Docker Compose; intended to run locally (no external network calls)

## Commands

```bash
# Install (host-side, for dev outside Docker)
cd frontend && npm install && cd ../backend && npm install

# Dev (run both together)
cd frontend && npm run dev        # port 1400; proxies /backend → localhost:1401
cd backend && npm run dev         # port 1401; nodemon, hot-reload

# Production build & run (Docker)
./run.sh prod build               # multi-stage Docker image (backend + frontend bundle)
./run.sh prod up [--watch]        # Start prod stack (backend serves built frontend)
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
4. User browses + moves items inside Explorer; user assigns subreddits to topics
5. Optional: `GET /download_db` to save the modified working DB locally

No data flows back to Expanse. Topic assignments are Explorer-local — they don't sync from Expanse uploads.

## Architecture

### Backend (`backend/controller/server.mjs`, `backend/model/db.mjs`)

Single Express server. Two endpoint families:

**Original (un-prefixed)** — Reddit user/item/move workflow:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/open_db` | Upload & merge a `.sqlite` (multipart, up to 1 GiB) |
| GET | `/users` | All users sorted by item count |
| GET | `/subs?user=` | Subreddits for a user with item counts |
| GET | `/items?user=&sub=` | Items for a user/subreddit |
| POST | `/move` | Move items between users (atomic, writes `moves` audit row) |
| POST | `/set_read` | Mark an item read/unread |
| GET | `/download_db` | Download current SQLite file |

**Topic family (`/api/` prefixed)** — category management + cross-user item browse:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/topics` | All topics with `sub_count`, `item_count` |
| POST | `/api/topics` | Add a topic (`{topic}`); 409 on duplicate |
| PATCH | `/api/topics` | Rename (`{old, new}`); 404 if `old` absent, 409 if `new` exists |
| DELETE | `/api/topics/:topic` | Delete + cascade-unmap subs (returns `cascaded_sub_topic_rows`) |
| GET | `/api/all_subs?topic=` | Subs filtered by topic; `__none__` → unmapped; omit → all |
| POST | `/api/assign_topic` | `{subs, topic}` (`topic: null` to unassign); upserts in one tx |
| GET | `/api/items_by_topic?topic=` | Items in a topic across all users (one row per `(item, username)` pair) |

**Why the `/api/` prefix on topic endpoints**: the SPA route `/topics` would otherwise collide with the un-prefixed `GET /topics`. The other endpoints don't need the prefix because no SPA route shadows them. If you add a SPA route that overlaps an existing un-prefixed endpoint, prefix the endpoint accordingly.

In dev mode (`RUN=dev`) CORS allows GET/POST/PATCH/DELETE/OPTIONS. In prod the built frontend is served as static files from the same Express process.

The catch-all (`app.all("*", …)`) serves `index.html` with status 200 as the SPA fallback (fixed in `5061726` — was 404 previously). Mistyped API URLs that don't match anything fall through to this and return HTML instead of JSON, which client code handles loudly via JSON parse error.

### Database Schema (`backend/model/db.mjs`)

WAL mode, foreign keys enabled. Key invariants: items are **never deleted**, only added; moves are **tracked** so a re-upload can't revert a user-initiated reassignment.

```
user_              (username PK, reddit_token, last_sync_epoch, …)
item               (id PK, type, content, author, sub, url, created_epoch)
user_item          (username, item_id, category, added_epoch, read_epoch — composite PK)
item_sub_icon_url  (sub PK, url)
item_fn_to_import  (id PK, fn_prefix)
moves              (item_id, from_username, from_category, to_username, to_category, moved_at_epoch)
topic              (topic PK)
sub_topic          (sub PK, topic FK — ON DELETE CASCADE + ON UPDATE CASCADE)
```

`merge_from_file(path)` runs inside a transaction; checks the `moves` table before assigning items so in-Explorer moves win over the uploaded file. **It does NOT touch `topic` / `sub_topic`** — those are local Explorer state and persist across uploads.

`init()` seeds 30 default topics via `insert or ignore` (idempotent — won't overwrite user renames). The seed array lives at the bottom of `init()`; edit it directly to change the seed list (existing installs need to insert any new ones manually).

The `sub_topic.topic` FK uses `ON UPDATE CASCADE` so renaming a topic is a single `UPDATE topic SET topic = ? WHERE topic = ?` and `sub_topic` rows follow automatically. Don't manually touch `sub_topic` rows on rename.

### Frontend (`frontend/source/`)

Multi-route SPA. Bootstrap 4.6 dark theme loaded via CDN in `app.html`. SSR disabled in `hooks.js`; static adapter in `svelte.config.js` outputs a client-side bundle. Vite alias `frontend` resolves to the frontend repo root so imports like `frontend/source/components/...` work.

**Routes:**

| File | URL | Purpose |
|------|-----|---------|
| `routes/__layout.svelte` | (wraps everything) | Top nav linking the two views; `.nav-active` underline on the current route |
| `routes/index.svelte` | `/` | User-first browse: pick user → pick sub → browse items + move |
| `routes/topics.svelte` | `/topics` | Manage Categories (add/rename inline/delete) + Categorize Subreddits (filter dropdown defaults to Uncategorized, multi-select subs, single-select target topic, Assign/Unassign) |
| `routes/topics/[topic].svelte` | `/topics/<name>` | Items in a topic across all users — full items table + cross-user move |

**Shared component:**

| File | Purpose |
|------|---------|
| `components/ItemsTable.svelte` | Virtual-scroll items table. Owns sort headers, hide-read filter, click-to-open + mark-read, checkbox column. Used by `/` and `/topics/<name>`. |

`ItemsTable` props:

```
items              raw items array
show_username      bool — adds a "user" column (true on /topics/<name>)
hide_read          bool — controlled by parent
read_overrides     Map — bind:read_overrides so parent can reset on reload
selected_item_ids  Set — bind:selected_item_ids for the parent's move action
on_set_read        (item, new_read) => void — parent decides which user to send to /set_read
```

Don't duplicate the virtual-scroll logic in a new route; pass props to `ItemsTable` instead.

Key patterns:
- **Virtual scrolling:** only visible rows + a 10-row buffer are rendered. Row height is 36 px desktop / 56 px mobile. Constants live in `ItemsTable.svelte`.
- **`read_overrides` map:** read state changes are applied locally first, then synced to `/set_read` in the background, so the UI stays responsive.
- **Backend URL:** `globals.js` sets `backend = ""` in prod (same origin) and `"/backend"` in dev (Vite proxy strips the prefix and forwards to port 1401).
- **Move from /topics/<name>:** items have a per-row `username`. `apply_move` groups the selection by source user and dispatches one `/move` per source — cross-user batch moves work in a single click.
- **Move target datalist:** both move forms use an HTML5 `<datalist>` populated from `/users` so existing users autocomplete in the input (added in commit `85d5d23`).

### Terminology — "category" vs "topic"

Two distinct meanings, do not conflate:

- **`user_item.category`** — the Reddit account collection type (saved / upvoted / submitted / etc.) that each row came from. Stored per-row in the existing schema.
- **`topic`** (UI label: "Category") — a topical grouping of subreddits (Jokes & Humor, Medicine, etc.). Stored in the new `topic` / `sub_topic` tables. **Global**: one mapping shared across all Reddit users in the DB.

The DB column / variable names use `topic` to avoid collision; the UI says "Category" because that's user-friendly.

### Uncategorized vs Miscellaneous

- **Uncategorized** = no `sub_topic` row for that sub. Default filter on `/topics`; shows your remaining categorization work.
- **Miscellaneous** = explicit `sub_topic.topic = 'Miscellaneous'`. The catch-all you assign a sub to once you've looked at it and decided it doesn't fit any themed bucket.

Don't conflate them. The two filters look similar but mean different things.

## Don'ts

- **Don't reuse a SPA route path for a new API endpoint.** The SPA owns `/`, `/topics`, `/topics/<name>`. New API endpoints that overlap need the `/api/` prefix (or pick a non-colliding path). See commit `2f57660` for the rationale.
- **Don't conflate `user_item.category` with the topic concept.** They're different. See the Terminology section.
- **Don't duplicate the items table.** It lives in `components/ItemsTable.svelte` and is shared. If you need a new column or behavior, prop-ify it on the component.
- **Don't touch `topic` / `sub_topic` in `merge_from_file`.** Those tables are local-only and must survive uploads.

## Recent changes worth remembering

- `5061726` — SPA fallback now returns 200 instead of 404.
- `2f57660` — Category-first organization: `topic` / `sub_topic` schema, 30-topic seed, `/api/topics` family, new `/topics` and `/topics/[topic]` routes, shared `ItemsTable` component.
- `85d5d23` — Move-target input gained a `<datalist>` of existing users for autocomplete.
