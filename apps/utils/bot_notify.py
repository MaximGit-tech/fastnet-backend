import requests
import os


BOT_WEBHOOK_URL = os.getenv('BOT_WEBHOOK_URL')
BOT_SECRET      = os.getenv("BOT_SECRET")

def notify_bot(telegram_id: int, event: str, data: dict):
    """
    Отправляет событие боту - бот шлёт сообщение пользователю
    """
    try:
        requests.post(
            BOT_WEBHOOK_URL,
            json={"telegram_id": telegram_id, "event": event, **data},
            headers={"X-Bot_secret": BOT_SECRET},
            timeout=5
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"notify_bot failed: {e}")
    