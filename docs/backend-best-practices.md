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
├─ main.py                     # app + router wiring, CORS
└─ api/
   ├─ health.py                # trivial single-endpoint routers stay flat
   ├─ darts.py                 # WebSocket router (vision pipeline)
   └─ <feature>/               # e.g. game/
      ├─ <feature>s.py         # APIRouter with the endpoints (e.g. games.py)
      ├─ dto/                  # Pydantic wire schemas (request/response)
      ├─ models/               # domain models (dataclasses) + business rules
      └─ services/             # stores, business logic, DTO mapping
```

- A **feature** gets its own folder under `api/` as soon as it needs more than a
  single router file.
- `dto/` — Pydantic models that cross the wire. Serialize with camelCase aliases
  so the JSON matches the Angular DTOs (a `CamelModel` base with
  `alias_generator=to_camel`, `populate_by_name=True`).
- `models/` — the domain: dataclasses plus the rules that operate on them. This
  is the source of truth for game logic (scores originate on the server).
- `services/` — stateful stores, orchestration, and mapping domain → DTO.
- Trivial single-endpoint routers (e.g. `health`) may stay as flat modules in
  `api/` until they grow into a feature.
- Namespace packages are used — no `__init__.py` files required.

## API Conventions
- Routers use an `APIRouter` with a `prefix` and `tags`; mount them in `main.py`
  under the shared `/api` prefix.
- Every endpoint declares a `response_model`; responses serialize by alias
  (camelCase) by default.
- Raise `HTTPException` with a clear `status_code` and `detail` for error cases.
- Validate inputs at the boundary (e.g. allowed game modes) before touching the
  domain layer.

## State & Persistence
- Game/session state is server-authoritative (see roadmap §4 and §7); the client
  holds only a synchronized cache.
- In-memory stores (module-level singletons) are fine for now, but note: state is
  lost on restart and not shared across worker processes. Persistence (Postgres)
  comes later.

## DTO ↔ Model Separation
- Keep Pydantic wire schemas (`dto/`) separate from domain models (`models/`).
- Map domain → DTO explicitly in `services/` (e.g. a `to_response(game)`
  function), so the wire format can evolve independently of the domain.
