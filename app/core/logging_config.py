import sys
from loguru import logger


def setup_logging(environment: str = "development") -> None:
    logger.remove()

    is_production = environment != "development"

    logger.add(
        sys.stdout,
        level="DEBUG" if is_production else "INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name} - {message}",
        colorize=not is_production,
        backtrace=is_production,
        diagnose=is_production,
    )

    if not is_production:
        logger.add(
            "logs/app.log",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} - {message}",
            rotation="10 MB",
            retention="30 days",
            encoding="utf-8",
        )

        logger.add(
            "logs/errors.log",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} - {message}\n{exception}",
            rotation="10 MB",
            retention="60 days",
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
        )
