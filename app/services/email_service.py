from loguru import logger


def send_confirmation_email(email: str, first_name: str) -> None:
    logger.info(f"[DEV] Confirmation email to {email}: Bienvenue {first_name}, votre compte M-Motors a été créé avec succès.")
