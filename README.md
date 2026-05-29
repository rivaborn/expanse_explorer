# expanse_explorer

A local browse/organize webapp for the SQLite exports produced by the
[Expanse](../expanse/) project (Reddit saved/upvoted/submitted scraper).
Reads the `.sqlite` you download from Expanse, lets you slice the corpus
by Reddit user **or** by topical category, reassign items between users,
and persistently group subreddits into categories so future uploads flow
into the right buckets automatically.

Runs entirely on `localhost`. No external network calls; no telemetry.

## What it does

- **Browse by user** — pick a Reddit account, then a subreddit, then
  read items. Virtual-scroll table over thousands of rows; click a row
  to open in a new tab and mark it read; sort by created or saved date;
  hide-read filter; multi-select + reassign items to a different user.
- **Browse by category** — assign each subreddit to a topical category
  once, then read items across every user grouped by topic. 30 default
  categories seeded; add / rename / delete your own via the UI. The
  mapping persists across new Expanse uploads, so re-importing pulls
  new posts into their existing buckets without re-categorizing.
- **Merge, don't replace** — uploading a new Expanse export merges
  into your working DB. Items already moved in Explorer stay where
  you put them (tracked via the `moves` audit table).
- **Round-trip** — download your working DB any time via the in-app
  Save button.

## Tech stack

- Frontend — SvelteKit (static-adapter SPA) + Bootstrap 4.6 dark theme
- Backend — Node.js + Express (ESM)
- Database — SQLite via `better-sqlite3`, single file at
  `backend/data/current.sqlite`
- Deployment — Docker Compose (single container in prod)

## Quick start (Docker)

```bash
./run.sh prod build       # multi-stage build (backend + frontend bundle)
./run.sh prod up          # serves on http://localhost:1401
```

Then open <http://localhost:1401>, click **load .sqlite** in the top
right, pick the file you got from Expanse, and start browsing.

## Quick start (dev, hot-reload)

```bash
# host-side install
cd backend  && npm install
cd ../frontend && npm install

# in two terminals
cd backend  && npm run dev      # :1401, nodemon
cd frontend && npm run dev      # :1400, vite (proxies /backend → :1401)
```

Frontend at <http://localhost:1400>; the dev server proxies API calls
through to the backend on `:1401`.

## Two views, two URLs

| URL | Purpose |
|-----|---------|
| `/` | Browse by Reddit user → subreddit → items |
| `/topics` | Manage categories (add / rename / delete) + assign subreddits to categories |
| `/topics/<name>` | Browse items in a category, across every Reddit user |

The 30 seed categories cover the highest-volume themes (Jokes, AITA,
Marriage, Infidelity, Books, Medicine, Finance, Tech, AI, Video Games,
Demographics Q&A, Politics, Sex, Erotica, etc.) plus a
**Miscellaneous** catch-all. They're just suggestions — edit the names,
add your own, delete the ones you don't use.

## How merging works

`POST /open_db` accepts a `.sqlite` upload and merges it into
`backend/data/current.sqlite`. The merge is **add-only**:

- New users / items / category icons / FN-import slugs are inserted.
- Existing user/item rows are left alone (the `moves` audit table
  records every reassignment, and uploaded data won't undo a move).
- Subreddit-to-category mappings (`topic` / `sub_topic` tables) are
  Explorer-local and untouched by the merge.

No data ever flows back to Expanse.

## REST API

Two families: the original Reddit-user/item workflow (unprefixed) and
the topic-management family (`/api/` prefixed to avoid colliding with
the SPA route `/topics`).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/open_db` | Upload & merge a `.sqlite` (multipart, up to 1 GiB) |
| GET | `/users` | All Reddit users by item count |
| GET | `/subs?user=` | Subreddits for a user |
| GET | `/items?user=&sub=` | Items for a user / sub |
| POST | `/move` | Reassign items to a different user |
| POST | `/set_read` | Mark an item read/unread |
| GET | `/download_db` | Download current `.sqlite` |
| GET | `/api/topics` | List categories + counts |
| POST | `/api/topics` | Add a category |
| PATCH | `/api/topics` | Rename `{old, new}` |
| DELETE | `/api/topics/:topic` | Delete (cascades to `sub_topic`) |
| GET | `/api/all_subs?topic=` | Subs filtered by category (`__none__` = unmapped) |
| POST | `/api/assign_topic` | `{subs, topic}` (`topic: null` to unassign) |
| GET | `/api/items_by_topic?topic=` | Items in a category, one row per (item, user) |

## Project layout

```
backend/
  controller/server.mjs    Express server + REST endpoints
  model/db.mjs             better-sqlite3 schema + queries + 30-topic seed
  data/                    [generated] current.sqlite + tmp/ uploads
frontend/
  source/
    app.html               Bootstrap 4.6 CSS via CDN
    globals.js             backend URL + app metadata
    hooks.js               SSR off
    components/
      ItemsTable.svelte    shared virtual-scroll items table
    routes/
      __layout.svelte      top nav + container
      index.svelte         "/" — user-first browse
      topics.svelte        "/topics" — manage + categorize
      topics/[topic].svelte "/topics/<name>" — items across all users
  svelte.config.js         static adapter, fallback index.html
compose.{dev,prod}.yaml    Docker Compose
dockerfile                 multi-stage (backend, frontend build, runtime)
run.sh                     `./run.sh {dev|prod} {build|up|down|update}`
CLAUDE.md                  deeper internals + Don'ts for future contributors
```

For deeper internals (DB invariants, naming-clash gotcha around
"category", endpoint-prefix rationale, ItemsTable contract), see
[CLAUDE.md](CLAUDE.md).

## Acknowledgments

Built around the SQLite shape produced by
[Expanse](../expanse/). The schema invariants — items never deleted,
moves audit-tracked — exist so an Explorer working DB can be re-merged
with newer Expanse exports without losing any in-Explorer reorganization.
