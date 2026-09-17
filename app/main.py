from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import __version__
from app.api.errors import registrar_handlers
from app.api.routes import enderecos, health
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=settings.http_timeout) as http_client:
        app.state.http_client = http_client
        yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Extrai endereços do ViaCEP, armazena no PostgreSQL e expõe para consulta."
    ),
    lifespan=lifespan,
)

registrar_handlers(app)
app.include_router(health.router)
app.include_router(enderecos.router, prefix="/api/v1")
