from pydantic import BaseModel


class CreateDetailsTopic(BaseModel):
    name: str
    category_name: str
