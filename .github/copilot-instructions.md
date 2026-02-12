# GitHub Copilot Instructions — Sidekick User Management API

## What This Project Is

A multi-tenant authorization microservice for an agent platform. It manages groups, group memberships with scoped roles (admin/user), and agent visibility across groups. The core platform handles agent creation and execution; this service handles who can do what.

## Tech Stack

- Python 3.12+, FastAPI, uvicorn
- uv for package management (not pip)
- Azure SQL (database), Redis (caching)
- Entra ID for authentication (JWT tokens)
- Docker for deployment to Azure App Service
- Splunk HEC for production logging

## Project Layout

- `src/app.py` — FastAPI entry point
- `src/base/` — Shared infrastructure (auth, middleware, config, utils). No domain logic here.
- `src/base/auth/auth_core.py` — JWT validation and role/scope checking
- `src/base/auth/rbac.py` — `require_roles_and_scopes` FastAPI dependency
- `src/base/core/lifespan.py` — Singleton service initialization at startup
- `src/base/core/dependencies.py` — FastAPI dependency injection getters for services
- `src/base/middleware/jwt_middleware.py` — JWT middleware with whitelist for public paths
- `src/base/middleware/correlation_middleware.py` — Correlation ID injection
- `src/domain/models/` — Pydantic request/response schemas and SQLAlchemy ORM models
- `src/domain/routes/` — API route handlers on `APIRouter` instances
- `src/domain/services/` — Business logic services (initialized as singletons in lifespan)

## Data Model

Five tables: `users`, `groups`, `group_memberships`, `agents`, `group_agents`.

- `users` — synced from JWT claims on each request (entra_object_id, display_name, email)
- `groups` — organizational units with name and description
- `group_memberships` — links users to groups with a role (admin or user). Unique on (entra_object_id, group_id)
- `agents` — registered agents with an external ID from the core platform
- `group_agents` — links agents to groups. Unique on (group_id, agent_id). An agent can be in multiple groups.

## Authorization Model

- **Superadmin**: Read from Entra ID group claim in JWT. Never stored locally. Can do everything.
- **Group admin**: Can manage members and agents within their group(s).
- **Group user**: Can access agents visible in their group(s).
- A group must always have at least one admin.
- Permission checks fail closed (deny if unreachable).

Two authorization decorators to use:
- `require_superadmin` — returns 403 if not superadmin
- `require_group_admin(group_id)` — returns 403 if not admin of specified group

## API Endpoints

Group CRUD: `POST/GET/PUT/DELETE /groups` and `/groups/{id}`
Membership: `POST/PUT/DELETE/GET /groups/{id}/members`
Agents: `POST /agents`, `POST/DELETE/GET /groups/{id}/agents`
Permissions: `GET /permissions/check`, `GET /users/{id}/agents`, `GET /users/{id}/admin-groups`
Admin: `GET /admin/agents`, `GET /admin/groups`, `PUT /admin/agents/{id}/groups`

## Code Style and Patterns

When generating code for this project:

- Use `logging.getLogger(__name__)` for logging in every module. Correlation IDs are injected automatically.
- Initialize services as singletons in `src/base/core/lifespan.py` and expose them through FastAPI dependency getters in `src/base/core/dependencies.py`.
- Put Pydantic models in `src/domain/models/`. Put route handlers in `src/domain/routes/`. Put business logic in `src/domain/services/`.
- Keep route handlers thin — delegate to services for business logic.
- Use `APIRouter` with `prefix` and `tags` for route modules.
- For new public endpoints, add the path to the `WHITELIST` in `src/base/middleware/jwt_middleware.py`.
- Use `os.getenv()` for environment variables. Use `is_local_development()` from `src/base/utils/env_utils.py` for environment-specific behavior.
- User data comes from JWT token claims — never call Graph API.
- Superadmin status is always read from the token, never stored in the database.
- Redis caching for permission checks. Invalidate cache on membership or agent-group changes.
- Use uv for dependency management, not pip.

## Don't

- Don't put domain/business logic in `src/base/`.
- Don't store superadmin status in the database.
- Don't call Microsoft Graph API for user info.
- Don't use pip — use uv (`uv sync`, `uv run`).
- Don't put business logic directly in route handlers.
- Don't skip cache invalidation when memberships or agent-group assignments change.
