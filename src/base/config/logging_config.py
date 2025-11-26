import logging

from src.base.middleware.correlation_middleware import CorrelationFilter


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
            handler = logging.StreamHandler()

            format_string = (
                "%(asctime)s | %(colored_levelname)s |%(filename_only)s | %(message)s"
            )
            formatter = ColoredFormatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

            handler.setFormatter(formatter)

            # Add correlation filter to include correlation ID in logs
            correlation_filter = CorrelationFilter()
            handler.addFilter(correlation_filter)

            logger.addHandler(handler)
