from pydantic import BaseModel


class DocumentRefuse(BaseModel):
    rejection_reason: str
