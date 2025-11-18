from pydantic import BaseModel


class PaymentCreateSchema(BaseModel):
    amount_vnd: float
    return_pathname: str = ""
    return_origin: str = ""
