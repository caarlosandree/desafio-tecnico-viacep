from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degradado"]
    banco: Literal["ok", "indisponível"]
