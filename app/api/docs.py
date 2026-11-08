from typing import Any

from fastapi.openapi.models import Example
from fastapi.routing import APIRoute

from .schemas.common import ErrorResponse

# Shown at the top of /docs and /scalar, Markdown works here
DESCRIPTION = """
Ship packages from **sellers** to **clients** through **delivery partners**.

## How to use it
1. Sign up as a seller (`POST /seller/signup`) or a partner (`POST /partner/signup`)
2. Log in with the **Authorize** button, or call `/seller/token` / `/partner/token`
3. Sellers create shipments, partners update them until delivery

## Errors
Every error has the same body: `{"detail": "what went wrong"}`.
Validation errors (422) list each wrong field instead.
"""

# One entry per router tag, in the order they appear in the docs.
# The names must match the tags on the routers exactly
TAGS_METADATA = [
    {
        "name": "Shipment",
        "description": "Create, track, update and cancel shipments.",
    },
    {
        "name": "Seller",
        "description": "Seller accounts. Sellers create the shipments.",
    },
    {
        "name": "Delivery Partner",
        "description": "Partner accounts. Partners deliver the shipments.",
    },
    {
        "name": "Tag",
        "description": "Predefined labels like `fragile`, with handling instructions.",
    },
]

# What each error code means in this API, reused by every endpoint
_ERRORS: dict[int, str] = {
    400: "The request can't be done, e.g. a wrong verification code",
    401: "Missing, invalid or expired access token, or a wrong password",
    403: "Logged in, but the shipment belongs to someone else",
    404: "Not found, e.g. the shipment doesn't exist",
    409: "Conflicts with the data, e.g. email taken or shipment cancelled",
    429: "Too many attempts, wait and try again",
}


def errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    # errors(401, 404) documents those two error responses on an endpoint
    return {
        code: {"model": ErrorResponse, "description": _ERRORS[code]}
        for code in codes
    }


# Named examples for the request body, the docs show them in a dropdown
SHIPMENT_EXAMPLES: dict[str, Example] = {
    "normal": {
        "summary": "A normal shipment",
        "value": {
            "content": "Glass vase",
            "weight": 2.5,
            "destination": 11001,
            "client_contact_email": "client@example.com",
        },
    },
    "with_phone": {
        "summary": "With an SMS number",
        "description": "The client gets the delivery code by SMS instead of email",
        "value": {
            "content": "Books",
            "weight": 4,
            "destination": 11001,
            "client_contact_email": "client@example.com",
            "client_contact_phone": "+201012345678",
        },
    },
    "too_heavy": {
        "summary": "Too heavy (fails with 422)",
        "value": {
            "content": "Fridge",
            "weight": 60,
            "destination": 11001,
            "client_contact_email": "client@example.com",
        },
    },
}


def operation_id(route: APIRoute) -> str:
    # Name each endpoint after its function, e.g. get_shipment instead of
    # get_shipment_shipment__get, so the generated frontend client is redable
    return route.name
