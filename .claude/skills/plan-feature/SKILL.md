---
name: plan-feature
description: Architecture pass before building a feature or any change that touches more than one file, a table, an endpoint or a view in this dart-tracking app. Use when asked to add, extend or rework functionality, and before fixing a bug whose cause is not a one-line slip. Produces a plan grounded in the existing code (reuse, layering, queries, paging, event loop, i18n, tests) instead of a quick fix.
---

# Plan a feature

Design first, code second. The goal is the solution that still fits when the data,
the number of users and the number of features grow, built from the blocks the app
already has.

## 1. Understand before designing

- Read the guidelines that apply: `docs/guidelines/backend-best-practices.md`,
  `docs/guidelines/frontend-best-practices.md`, and the issue if there is one.
- Find the closest existing feature and follow its shape. Search `frontend/src/app/core/`
  (`view/components`, `view/models`, `view/services`, `charts`) and the backend's
  `api/core/` before inventing anything.
- For a bug: find the root cause and the layer it belongs to. A fix in the wrong layer
  (a guard in the template for bad server data, a special case for one input) is a
  quick fix — name the real cause and fix it there.

## 2. Design checklist

Go through every point; skip one only when it plainly does not apply.

**Backend structure**
- Which feature folder under `backend/src/app/api/features/` owns it? Router, `dto/`,
  `domain/`, `persistence/`, `services/` as in the guidelines; `dto/` imports `domain/`,
  never the reverse; domain → DTO via `from_entity()`.
- Closed value sets are enums in `domain/` used as DTO field types, not manual checks.
- Rules live in `domain/` and are server-authoritative; the client only displays.

**Data and queries**
- Schema change → an Alembic migration, the table module listed in `api/tables.py`.
- No query per row (N+1). The repositories declare no relationships: load the parent
  rows, then fetch children for all of them at once with `.in_(ids)` and group in
  Python (see `game_repository.py`). Never query inside a loop over rows.
- Counts, sums and aggregates run in SQL (`func.count`, `group_by`), not by loading rows.
- Columns used in `where`, `order_by` or joins of a growing table get an index.
- Lists from the server are paged on the server: `limit`, `offset`, filters in,
  `{ items, total }` out, with the total from one `count` query.
- Hot, game-scoped state goes to Redis with a TTL; durable data to Postgres.

**Event loop**
- Anything CPU-heavy or growing with the account's data runs through
  `asyncio.to_thread` on rows already loaded; add a case to
  `tests/unit/test_event_loop.py`.

**API**
- Every endpoint has a `response_model`, camelCase via `CamelModel`, English error codes
  in `detail`. Think about who may call it (auth optional, foreign data → 403/404).
- Prefer one endpoint that returns what the view needs over several round trips.

**Frontend**
- Feature folder layout (`components/`, `dto/`, `models/`, `services/`), standalone
  components with OnPush, signals and `computed()`, `input()`/`output()`, lazy route.
- Reuse the shared blocks named in "Consistency and reuse": `app-loading-state`,
  `app-empty-state`, `app-load-error`, `app-field-error`, `p-table.data-table` with
  `PagedTable`, `app-list-toolbar`, `ConfirmService`, `DIALOG_STYLE`, `chartBase()`.
- Use a PrimeNG component wherever one exists; check its API through the PrimeNG MCP
  server or docs instead of guessing. Hand-written CSS only for layout and for what the
  theme cannot express, with `var(--p-…)` tokens.
- Mobile first: the layout is designed for 375 px wide, control rows fit on one line.
- Every new text gets an i18n id and an English translation (`npm run i18n`).

**Tests**
- Every backend change gets pytest cases: rules in `tests/unit/`, endpoints in
  `tests/api/`. Include a case that would catch the N+1 or paging edge if relevant.

## 3. Write the plan

Keep it short and concrete:
1. **Goal** in one sentence.
2. **Approach**: the design, and in one line each the alternative not taken and why.
3. **Changes** per layer: files to create or change, with the existing block reused.
4. **Data**: migration, queries (how many per request), indexes.
5. **Risks / open points**: only real ones.
6. **Tests** to add.

Then build it in that order: domain and persistence, service, API, frontend, tests.
If the work drifts from the plan, update the plan rather than patching around it.
