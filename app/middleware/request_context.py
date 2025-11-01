from starlette.middleware.base import BaseHTTPMiddleware

from app.core.context import current_request


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Lưu Request hiện tại vào context để lấy lại ở service."""

    async def dispatch(self, request, call_next):
        token = current_request.set(request)
        try:
            response = await call_next(request)
        finally:
            current_request.reset(token)
        return response
