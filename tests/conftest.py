import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app import models  # noqa: F401  (registra os models no metadata)
from app.core.config import get_settings
from app.db.base import Base


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session():
    """Sessão ligada a uma transação que é desfeita ao fim de cada teste."""
    engine = create_async_engine(get_settings().database_url)
    try:
        conexao = await engine.connect()
    except OperationalError:
        await engine.dispose()
        pytest.skip("Postgres indisponível: rode `docker compose up -d db`")

    transacao = await conexao.begin()
    await conexao.run_sync(Base.metadata.create_all)
    sessao = AsyncSession(
        bind=conexao,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield sessao
    finally:
        await sessao.close()
        await transacao.rollback()
        await conexao.close()
        await engine.dispose()
