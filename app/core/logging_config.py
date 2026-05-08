import sys
from loguru import logger


def setup_logging() -> None:
    logger.remove()

    # Console : niveau INFO, format lisible
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Fichier applicatif : tous les niveaux, rotation 10 Mo, 30 jours de rétention
    logger.add(
        "logs/app.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )

    # Fichier dédié aux erreurs uniquement
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
