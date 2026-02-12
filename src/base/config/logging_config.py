import logging
import os

from src.base.config.splunk_handler import AsyncSplunkHECHandler
from src.base.middleware.request_context import RequestContextFilter
from src.base.utils.env_utils import is_local_development


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = (
                f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            )
            record.colored_levelname = colored_levelname
        else:
            record.colored_levelname = f"{levelname}"

        # Extract just the filename from the full module path
        if hasattr(record, "name") and record.name:
            # Split by dots and take the last part (filename)
            filename = record.name.split(".")[-1]
            # If it's __main__, use 'app' instead
            record.filename_only = filename if filename != "__main__" else "app"
        else:
            record.filename_only = "unknown"

        return super().format(record)


class LoggingConfig:
    """Configuration class for application logging setup."""

    splunk_handler: AsyncSplunkHECHandler | None = None

    @staticmethod
    def setup_logging(log_level: int = logging.INFO) -> None:
        """
        Configure application logging with correlation ID support and improved formatting.

        Args:
            log_level: The logging level (default: logging.INFO)
        """
        logger = logging.getLogger()
        logger.setLevel(log_level)

        # Only add handlers if none exist to avoid duplicates
        if not logger.hasHandlers():
            # Add correlation filter to include correlation ID in logs
            context_filter = RequestContextFilter()
            filters = [context_filter]

            LoggingConfig.add_console_logging(logger, filters)

            # Add Splunk logging if not local development
            if not is_local_development():
                LoggingConfig.add_splunk_logging(logger, filters)

    @staticmethod
    def add_console_logging(
        logger: logging.Logger, filters: list[logging.Filter]
    ) -> None:
        # Console handler with colored output
        handler = logging.StreamHandler()

        format_string = (
            "%(asctime)s | %(colored_levelname)s |%(filename_only)s | %(message)s"
        )
        formatter = ColoredFormatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)

        for filter in filters:
            handler.addFilter(filter)

        logger.addHandler(handler)

    @staticmethod
    def add_splunk_logging(
        logger: logging.Logger, filters: list[logging.Filter]
    ) -> None:
        # Splunk HEC handler (requires SPLUNK_TOKEN to be configured)
        splunk_token = os.getenv("SPLUNK_TOKEN", "")
        host = os.getenv("SPLUNK_HOST", "")
        url = os.getenv("SPLUNK_URL", "")
        application_name = os.getenv(
            "SPLUNK_APPLICATION_NAME", "sidekick-user-management-api"
        )

        if not (splunk_token and host and url):
            logger.warning(
                "Splunk logging is enabled but SPLUNK_TOKEN, SPLUNK_HOST, or SPLUNK_URL is not set. Skipping Splunk logging setup."
            )
            return

        LoggingConfig.splunk_handler = AsyncSplunkHECHandler(
            host=host,
            token=splunk_token,
            url=url,
            application_name=application_name,
        )
        for filter in filters:
            LoggingConfig.splunk_handler.addFilter(filter)

        logger.addHandler(LoggingConfig.splunk_handler)
