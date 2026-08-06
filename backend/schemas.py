from pydantic import BaseModel

class CustomerCreate(BaseModel):
    name: str
    usage: float
    tickets: int
    nps: int
    renewal_status: str

class CustomerResponse(CustomerCreate):
    id: int

    class Config:
        from_attributes = True
