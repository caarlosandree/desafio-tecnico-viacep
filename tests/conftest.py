import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app import models  # noqa: F401  (registra os models no metadata)
from app.core.config import get_settings
from app.db.base import Base
from tests.fakes import COPACABANA, PAULISTA, SE, ViaCepFake


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def database_url() -> str:
    """URL de um banco exclusivo para testes, criado se ainda não existir.

    Usa TEST_DATABASE_URL, se definida; senão, o banco da aplicação com sufixo _test.
    """
    if url_env := os.getenv("TEST_DATABASE_URL"):
        url = make_url(url_env)
    else:
        url = make_url(get_settings().database_url)
        url = url.set(database=f"{url.database}_test")

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conexao:
            existe = conexao.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :nome"),
                {"nome": url.database},
            )
            if not existe:
                conexao.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError:
        pytest.skip("Postgres indisponível: rode `docker compose up -d db`")
    finally:
        admin.dispose()

    return url.render_as_string(hide_password=False)


@pytest.fixture
async def session(database_url):
    """Sessão ligada a uma transação que é desfeita ao fim de cada teste."""
    engine = create_async_engine(database_url)
    conexao = await engine.connect()

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


@pytest.fixture
def viacep() -> ViaCepFake:
    return ViaCepFake(SE, PAULISTA, COPACABANA)
