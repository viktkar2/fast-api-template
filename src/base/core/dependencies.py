from src.domain.services.example_service import ExampleService
from fastapi import Request


def get_example_service(request: Request) -> ExampleService:
    """Return the singleton ExampleService instance from app state."""
    return request.app.state.example_service
