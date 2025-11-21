import uuid

from pydantic import BaseModel


class WithdrawApproveDenySchema(BaseModel):
    approve: bool
    withdraw_ids: list[uuid.UUID] | None = None
    all_pending: bool = False
    reason: str | None = None
    lecturer_id: uuid.UUID | None = None
