from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PresenceStatus = Literal["online", "offline", "away"]


class PresenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    status: PresenceStatus
    last_seen_at: datetime | None = None
    connection_count: int = 0


class PresenceBulkRequest(BaseModel):
    user_ids: list[str] = Field(default_factory=list, max_length=200)


class PresenceBulkResponse(BaseModel):
    users: dict[str, PresenceResponse]
