from typing import ClassVar

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class FastShipError(Exception):
    """"Base class for every error the app raises on purpose"""
    
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Something went wrong"
    headers: ClassVar[dict[str, str] | None] = None
    
    def __init__(self, detail: str | None = None):
        # Each error has a default message, a different one can be passed
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)
    

class InvalidInput(FastShipError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Invalid input"


class NotAuthenticated(FastShipError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid or expired access token"
    # The OAuth2 standard asks 401 responses to name the auth scheme
    headers: ClassVar[dict[str, str] | None] = {"WWW-Authenticate": "Bearer"}
    
    
class InvalidCredentials(NotAuthenticated):
    detail = "Email or password is incorrect"
    

class NotAllowed(FastShipError):
    # Logged in, but this resource belongs to someone else
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You are not allowed to do this" 
    

class EntityNotFound(FastShipError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Not found"
    

class AlreadyExists(FastShipError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Already exists"
    

class InvalidState(FastShipError):
    # The request is fine, but the shipment's current status doesn't allow it
    status_code = status.HTTP_409_CONFLICT
    detail = "Not allowed in the current state"
    

class NoPartnerAvailable(FastShipError):
    status_code = status.HTTP_409_CONFLICT
    detail = "No delivery partner available"
    

class TooManyAttempts(FastShipError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Too many attempts"
    

def add_exception_handlers(app: FastAPI):
    @app.exception_handler(FastShipError)
    async def handle_fastship_error(request: Request, exc: FastShipError):
        # Same {"detail": ...} shape as FastAPI's own errors, so clients see one format
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    
    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # A bug: hide the details from the client. The full traceback is still
        # printed in the terminal, because Starlette re-raise it after this response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )