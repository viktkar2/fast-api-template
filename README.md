# FastAPI + Azure AD RBAC Authentication

A FastAPI application demonstrating Azure Active Directory integration with Role-Based Access Control (RBAC) and WebSocket support.

## Features

- FastAPI web framework
- Azure AD authentication with JWT tokens
- Role-Based Access Control (RBAC)
- WebSocket endpoints with authentication
- Public and private endpoints

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Azure AD tenant with configured application

## Installation

1. **Clone the repository** (if not already done):

   ```bash
   git clone <repository-url>
   cd py-test-auth
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Configure environment variables**:

   ```bash
   # Copy the example environment file
   copy .env.example .env
   ```

   Edit `.env` file with your Azure AD configuration

   ```bash
   # Application environment
   ENVIRONMENT=development

   # Azure AD
   AZURE_TENANT_ID=your-tenant-id
   AZURE_CLIENT_ID=your-client-id
   AZURE_AUDIENCE=your-audience
   AZURE_SCOPE=your-scope
   ```

## Running the Application

### Development Server

Run the application using uv:

```bash
# From the project root directory
uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker compose up --build
```

The application will be available at:

- **Main application**: http://localhost:8000
- **API documentation**: http://localhost:8000/docs

## API Endpoints

### HTTP Endpoints

- **GET /api/public** - Public endpoint, no authentication required
- **GET /api/private** - Private endpoint, requires valid JWT token

### WebSocket Endpoints

- **WS /api/ws/public** - Public WebSocket, no authentication required
- **WS /api/ws/private** - Private WebSocket, requires authentication

## Authentication

The application uses Azure AD JWT tokens for authentication. Include the token in the Authorization header:

```bash
Authorization: Bearer <your-jwt-token>
```

## Testing the Application

### Test Public Endpoint

```bash
curl http://localhost:8000/api/public
```

### Test Private Endpoint

```bash
curl -H "Authorization: Bearer <your-token>" http://localhost:8000/api/private
```

### WebSocket Testing

You can test WebSocket endpoints using tools like:

- WebSocket clients (e.g., wscat)
- Browser developer tools
- Postman

Example with wscat:

```bash
# Install wscat if not already installed
npm install -g wscat

# Test public WebSocket
wscat -c ws://localhost:8000/api/ws/public
```

## Project Structure

```
src/
├── app.py                    # Main FastAPI application
├── base/
|   ├── core/
│   │   ├── lifespan.py       # Instantiate singleton services 
│   │   └── dependencies.py   # Getters for available singleton services
│   ├── auth/                 # Authentication modules
│   │   ├── auth_core.py      # Core authentication logic
│   │   ├── rbac.py           # Role-based access control
│   │   └── websocket_auth.py # WebSocket authentication
│   ├── decorators/           # Custom decorators
│   └── middleware/           # Custom middleware
│       └── jwt_middleware.py # JWT middleware
└── domain/
    ├── models/               # Data models
    │   └── models.py
    └── routes/               # API routes
        ├── routes.py         # HTTP routes
        └── ws_routes.py      # WebSocket routes
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're running from the project root directory
2. **Authentication failures**: Verify Azure AD configuration in `.env` file
3. **Port conflicts**: Change the port using `--port` parameter

### Logs

The application logs are configured to output to the console. Check the terminal output for debugging information.
