from typing import Optional

from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    fullname: str
    bio: Optional[str] = None
    facebook_url: Optional[str] = None
    birthday: Optional[str] = None
    conscious: Optional[str] = None
    district: Optional[str] = None
    citizenship_identity: Optional[str] = None
