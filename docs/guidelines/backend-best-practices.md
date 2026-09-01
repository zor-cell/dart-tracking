You are an expert in Python, FastAPI, and building maintainable backend services. You write typed, testable, feature-organized code following FastAPI and Python best practices.

## Python Best Practices
- Target Python 3.12+; use modern typing (`X | None`, builtin generics like `list[...]`).
- Use type hints everywhere; keep functions small and single-purpose.
- Comments in code are always written in English.

## Project Structure
The backend mirrors the frontend's feature-first layout. Each feature is a folder
under `src/app/api/` that owns everything for that feature, grouped by type:

```
src/app/
├─ main.py                     # app + router wiring, CORS, lifespan
├─ infrastructure/             # process plumbing; knows nothing about darts
│  ├─ config.py                # Settings (pydantic-settings), reads the root .env
│  ├─ database.py              # async SQLAlchemy engine, session factory, Base
│  └─ redis_client.py          # async Redis client
└─ api/
   ├─ health.py                # trivial single-endpoint routers stay flat
   ├─ core/
   │  ├─ domain/               # cross-feature domain models (client.py, device_role.py)
   │  ├─ dto/                  # cross-feature wire schemas (base.py)
   │  ├─ services/             # cross-feature stores (client_store.py)
   │  └─ socket/               # the single WebSocket endpoint (vision pipeline entry point),
   │                           # with its own dto/ and services/ (game_hub.py)
   └─ features/
      └─ <feature>/            # e.g. game/, calibration/, detection/
         ├─ <feature>s.py      # APIRouter with the endpoints, if the feature has REST ones (e.g. games.py)
         ├─ dto/               # Pydantic wire schemas (request/response)
         ├─ domain/            # domain models (dataclasses) + business rules
         ├─ debug/             # diagnostics: the run trace and its renderer (CV features only)
         └─ services/          # stores and orchestration
```

- `infrastructure/` — configuration and the connections the process owns, opened
  and closed by `main.lifespan`. Sits outside `api/` because it carries no
  domain, no wire schema and no feature; `api/` imports from it, never the
  reverse. Deliberately not called `core/`: that name is already taken one level
  down by `api/core/`, and two different `core`s would be a permanent source of
  confusion. Not `config/` either — an engine with a connection pool is not
  configuration.
- A **feature** gets its own folder under `api/features/` as soon as it needs
  more than a single router file.
- `dto/` — Pydantic models that cross the wire. Serialize with camelCase aliases
  so the JSON matches the Angular DTOs (a `CamelModel` base with
  `alias_generator=to_camel`, `populate_by_name=True`).
- `domain/` — the domain: dataclasses plus the rules that operate on them, the
  enums that name its closed sets, and its fixed constants (`board_geometry.py`).
  This is the source of truth for game logic (scores originate on the server).
  Named `domain/` rather than `entity/` because nothing here is persisted — the
  Java/JPA reading of "entity" (a row in a table) does not apply — and rather
  than `models/`, which in a FastAPI codebase reads as the Pydantic models that
  already live in `dto/`.
- `debug/` — what a pipeline run saw, and how to look at it: a trace dataclass
  the service fills as it goes, plus the renderer that turns it into one image
  per stage. Only the CV features have one. This is **not** dev-only tooling: the
  socket endpoint renders live when a frame arrives with `debug: true`, which is
  what the frontend's debug switches drive. The CLI runners that replay photos
  off disk stay in `backend/scripts/` — they are entry points, not app code.
  - The detector owns a module-level `trace` that it replaces on each run, so
    `services/` imports `debug/trace.py`. That direction is deliberate;
    `trace.py` imports nothing from `services/`, so there is no cycle.
- `services/` — stateful stores and orchestration.
- Trivial single-endpoint routers (e.g. `health`) may stay as flat modules in
  `api/` until they grow into a feature.
- `core/socket.py` owns the WebSocket endpoint but no domain logic: it decodes
  the incoming message and dispatches to whichever feature's DTOs and services
  handle that message type (calibration, detection, game). Importing
  feature-specific `dto`/`services` there is the one deliberate exception to
  `core` not depending on `features` — the same aggregation-point pattern the
  frontend uses in `core/socket/dto/socket-message.ts`.
- **No `__init__.py` files anywhere** — the whole tree uses implicit namespace
  packages (PEP 420, Python 3.3+). Do not add them back.
  - This works because the project is never installed as a distribution: there is
    no `[build-system]` in `pyproject.toml`, so `uv sync` installs only the
    dependencies. `app` is resolved purely through `sys.path`, which
    `--app-dir src` sets up in dev and in the Dockerfile alike.
  - Consequence to keep in mind: adding a `[build-system]` later would break
    this, because setuptools' auto-discovery skips directories without
    `__init__.py`. If it ever becomes a real package, switch the discovery to
    `find_namespace_packages()` rather than sprinkling `__init__.py` files.

## API Conventions
- Routers use an `APIRouter` with a `prefix` and `tags`; mount them in `main.py`
  under the shared `/api` prefix.
- Every endpoint declares a `response_model`; responses serialize by alias
  (camelCase) by default.
- Raise `HTTPException` with a clear `status_code` and `detail` for error cases.
- Validate inputs at the boundary by **typing** them, not by hand-written checks.
  A closed set of values belongs in an `Enum` in `domain/` (see `GameMode`), used
  as the field type in the DTO: pydantic then rejects anything else with a 422,
  and the value shows up as a proper `enum` in the OpenAPI schema. Reach for a
  manual `HTTPException` only for rules the type system cannot express (e.g. "at
  least one player").
- Prefer `IntEnum`/`StrEnum` when the value carries meaning (`GameMode` *is* the
  starting score): arithmetic keeps working and the JSON stays a plain number, so
  the wire format does not change.

## State & Persistence
- Game/session state is server-authoritative (see roadmap §4 and §7); the client
  holds only a synchronized cache.
- In-memory stores (module-level singletons) are fine for now, but note: state is
  lost on restart and not shared across worker processes. Persistence (Postgres)
  comes later.

## DTO ↔ Domain Separation
- Keep Pydantic wire schemas (`dto/`) separate from domain models (`domain/`).
- The dependency points **one way only**: `dto/` may import `domain/`, never the
  reverse. The domain must not know how it is serialized — otherwise the game
  rules end up coupled to camelCase JSON, and a second wire format (the
  WebSocket `game_state` push) would have to be modelled inside the domain too.
- Map domain → DTO with a `from_entity()` classmethod on the DTO. Construction
  lives next to the schema it builds, and routers read as
  `GameStateDto.from_entity(game)`.
- Values that belong to the aggregate rather than to the mapped object are
  passed in explicitly (e.g. `PlayerDto.from_entity(player, remaining)`, since
  the remaining score is derived from the game's turn history).
