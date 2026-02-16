# Sidekick User Management API

Multi-tenant authorization microservice for the Sidekick agent platform. Manages groups, group memberships with scoped roles, and agent visibility across groups.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure AD tenant with configured application
- MongoDB (or Azure Cosmos DB for MongoDB in production)

## Setup

1. **Install dependencies**:

   ```bash
   uv sync
   ```

2. **Configure environment variables**:

   ```bash
   copy .env.example .env
   ```

   Edit `.env` with your Azure AD and database configuration:

   ```bash
   ENVIRONMENT=development

   # Azure AD
   AZURE_TENANT_ID=your-tenant-id
   AZURE_CLIENT_ID=your-client-id
   AZURE_SCOPE=your-scope

   # MongoDB
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DATABASE=sidekick
   ```

## Running

### Development Server

```bash
uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
```

When `ENVIRONMENT=development`, the app automatically falls back to an in-memory MongoDB mock if no real MongoDB instance is reachable. Data will not persist across restarts in this mode.

To run with a real MongoDB (persistent data), start the infrastructure containers first:

```bash
docker compose up mongo redis
uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker compose up --build
```

The application will be available at:

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs

## Database

The application uses [Beanie ODM](https://beanie-odm.dev/) with MongoDB (Azure Cosmos DB for MongoDB in production). Indexes are created automatically on application startup via `init_beanie()` — no migration tool is needed.

## Testing

```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_authorization.py -v

# Run linter
uv run ruff check src/

# Run formatter
uv run ruff format src/
```

Tests use `mongomock-motor` for an in-memory MongoDB mock — no running MongoDB instance is required.

## Project Structure

```
src/
├── app.py                              # FastAPI app entry point
├── base/                               # Shared infrastructure (no domain logic)
│   ├── auth/                           # JWT validation, token-level RBAC
│   ├── config/                         # Logging, OpenAPI, Splunk, database
│   ├── core/                           # App lifespan, dependency injection
│   ├── middleware/                      # JWT and correlation ID middleware
│   └── utils/                          # Environment helpers
└── domain/                             # Business logic
    ├── auth/                           # Domain authorization (group admin checks)
    ├── models/                         # Pydantic schemas, Beanie Document models
    ├── routes/                         # API route handlers
    └── services/                       # Business logic services

tests/                                  # Test suite
docs/                                   # Documentation
```

## Authentication

The application uses Azure AD JWT tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

- **Authentication** (identity) is handled by Entra ID
- **Authorization** (permissions) is handled by this microservice — see `src/domain/auth/`
