from pydantic import BaseModel


class CreateRole(BaseModel):
    role_name: str
    details: str


class UpadteRole(BaseModel):
    role_name: str
    details: str
