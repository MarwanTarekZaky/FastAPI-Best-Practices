# The image for the API, the Celery worker and the migrations: one image,
# a different command for each
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN useradd --system --no-create-home fastship
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
USER fastship
EXPOSE 8000
CMD [ "fastapi", "run", "app/main.py", "--port", "8000", "--forwarded-allow-ips", "*" ]