import logging
from typing import Any

import logfire
from fastapi import FastAPI

from app.config import app_settings
from app.database.session import engine


def _configure(service_name: str, distributed_tracing: bool):
    logfire.configure(
        # Shown on every span, so the API and the worker can be told apart
        service_name=service_name,
        environment=app_settings.ENVIRONMENT,
        token=app_settings.LOGFIRE_TOKEN,
        # Without a token (tests, a machine without one) nothing is sent anywhere
        send_to_logfire="if-token-present",
        # Our own logging already prints to the terminal
        console=False,
        # Whether to continue a trace that arrives from outside, see the callers
        distributed_tracing=distributed_tracing,
    )
    # Our log lines also go to Logfire, attached to the request that wrote them
    logging.getLogger("app").addHandler(logfire.LogfireLoggingHandler())


def _request_attributes(request: Any, attributes: dict[str, Any]) -> dict[str, Any]:
    # By default every endpoint argument is recorded. Ours hold emails, phone
    # numbers and the login form, so keep only the validation errors
    return {"errors": attributes["errors"]} if attributes["errors"] else {}


def setup_telemetry(app: FastAPI):
    # Anyone on the internet can send a trace id header, don't join their traces
    _configure("fastship-api", distributed_tracing=False)
    # One span (a timed step) per request: route, status code and duration.
    # /health is called every few seconds by Docker and Render, skip it
    logfire.instrument_fastapi(
        app,
        excluded_urls="/health",
        request_attributes_mapper=_request_attributes,
    )
    # One span per SQL query and per Redis command, inside the request's span.
    # skip_dep_check: the instrumentation lists SQLAlchemy < 2.1, we have 2.1.
    # tests/unit/test_telemetry.py checks that the query spans still work
    logfire.instrument_sqlalchemy(engine=engine, skip_dep_check=True)
    logfire.instrument_redis()
    # Puts the trace id in each task message, so the worker continues the trace
    logfire.instrument_celery()


def setup_worker_telemetry():
    # Task messages come from our own API: continue the API's trace
    _configure("fastship-worker", distributed_tracing=True)
    logfire.instrument_celery()
    logfire.instrument_redis()
