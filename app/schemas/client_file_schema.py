from pydantic import BaseModel
from app.models.client_file import ClientFileType


class ClientFileCreate(BaseModel):
    vehicle_id: int
    file_type: ClientFileType


class ClientFileStatusUpdate(BaseModel):
    status: str
