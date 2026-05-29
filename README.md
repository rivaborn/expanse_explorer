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

## Three views, three URLs

| URL | Purpose |
|-----|---------|
| `/` | **Browse by category** (default) — pick a category, see items across every Reddit user |
| `/by_user` | Browse by Reddit user → subreddit → items |
| `/topics` | Manage categories (add / rename / delete) + assign subreddits to categories |
| `/topics/<name>` | Deep-link variant of `/` for a specific category |

The 30 seed categories cover the highest-volume themes (Jokes, AITA,
Marriage, Infidelity, Books, Medicine, Finance, Tech, AI, Video Games,
Demographics Q&A, Politics, Sex, Erotica, etc.) plus a
**Miscellaneous** catch-all. They're just suggestions — edit the names,
add your own, delete the ones you don't use.

For bulk first-pass categorization of every subreddit in your DB, run
`scripts/categorize_subs.py --apply`. It uses an explicit seed list per
category plus a keyword/regex heuristic for the long tail, then POSTs
to `/api/assign_topic`. Anything that doesn't match a rule lands in
Miscellaneous. Safe to re-run after a new upload — it only touches
Uncategorized subs.

## How merging works

`POST /open_db` accepts a `.sqlite` upload and merges it into
`backend/data/current.sqlite`. The merge is **add-only** and treats
your in-Explorer changes as the source of truth.

What survives a re-upload:

- **Moves you made.** The `moves` audit row blocks re-assignment of
  any item back to its old user.
- **Read state.** Existing `user_item.read_epoch` is never touched.
- **Topic assignments.** `topic` / `sub_topic` are Explorer-local and
  not part of the merge at all.
- **Item content.** If the upload has a different version of an item
  with the same id, the original wins.

What the merge does:

- Inserts new items / users / category icons / FN-import slugs.
- Inserts new `user_item` assignments where you don't already have
  that `(user, category, item)` triple **and** the item wasn't moved
  away from that user.
- Upserts `user_` tokens (non-null wins) and updates epochs to the
  newer value.
- Backfills `user_item.added_epoch` on existing rows that were NULL.

What it doesn't do:

- Doesn't delete anything, ever.
- Doesn't touch your topic mappings — new subreddits in the upload
  show up under **Uncategorized** until you assign them.
- Doesn't send anything back to Expanse.

The whole thing runs in a single SQLite transaction; rollback on any
error leaves the DB untouched.

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
      index.svelte         "/" — browse by category (default landing)
      by_user.svelte       "/by_user" — user-first browse
      topics.svelte        "/topics" — manage + categorize
      topics/[topic].svelte "/topics/<name>" — deep-link variant of "/" for one category
  svelte.config.js         static adapter, fallback index.html
scripts/
  categorize_subs.py       one-shot bulk subreddit-to-category assigner
                           (regex/keyword heuristic; --apply to POST)
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
