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
    instructor_description: Optional[str] = None
    # Learning goals
    learning_goals: Optional[str] = None
    daily_goal_minutes: Optional[int] = None
    preferred_learning_style: Optional[str] = None
