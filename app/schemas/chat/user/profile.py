from pydantic import BaseModel


class CreateBioSchema(BaseModel):
    request: str
