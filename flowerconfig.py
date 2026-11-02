from app.config import celery_settings

# Flower reads this file automatically
basic_auth = [f"{celery_settings.FLOWER_USER}:{celery_settings.FLOWER_PASSWORD}"]
address = "127.0.0.1"
port = 5555
