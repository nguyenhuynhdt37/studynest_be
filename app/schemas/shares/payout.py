from pydantic import BaseModel


class PayoutInfo(BaseModel):
    return_pathname: str = ""
    return_origin: str = ""
