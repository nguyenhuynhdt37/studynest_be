from contextvars import ContextVar

from fastapi import Request

current_request: ContextVar[Request | None] = ContextVar(
    "current_request", default=None
)


def get_request() -> Request:
    req = current_request.get()
    if req is None:
        raise RuntimeError(
            "Không tìm thấy Request trong context — quên thêm middleware rồi!"
        )
    return req
