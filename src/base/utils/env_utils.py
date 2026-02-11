"""
Environment utilities
"""

import os


def is_local_development() -> bool:
    """
    Check if the application is running in local development environment.

    Returns:
        bool: True if running in local development, False otherwise.
    """
    environment = os.getenv("ENVIRONMENT", "").lower()
    return environment == "development"
