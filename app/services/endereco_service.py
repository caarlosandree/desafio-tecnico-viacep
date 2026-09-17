from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.viacep import ViaCepClient, normalizar_cep
from app.models import Endereco


class EnderecoService:
    def __init__(self, session: AsyncSession, viacep: ViaCepClient) -> None:
        self._session = session
        self._viacep = viacep

    async def importar(self, cep: str) -> Endereco:
        """Consulta o ViaCEP e grava o endereço, atualizando-o se o CEP já existir."""
        dados = (await self._viacep.buscar(cep)).model_dump()

        stmt = insert(Endereco).values(**dados)
        campos_atualizados = {
            campo: stmt.excluded[campo] for campo in dados if campo != "cep"
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[Endereco.cep],
            set_={**campos_atualizados, "updated_at": func.now()},
        ).returning(Endereco)

        endereco = await self._session.scalar(
            stmt, execution_options={"populate_existing": True}
        )

        await self._session.commit()
        return endereco

    async def obter(self, cep: str) -> Endereco | None:
        stmt = select(Endereco).where(Endereco.cep == normalizar_cep(cep))
        return await self._session.scalar(stmt)

    async def listar(
        self,
        *,
        uf: str | None = None,
        localidade: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Endereco], int]:
        filtros = []
        if uf:
            filtros.append(Endereco.uf == uf.upper())
        if localidade:
            filtros.append(Endereco.localidade.icontains(localidade, autoescape=True))

        total = await self._session.scalar(
            select(func.count()).select_from(Endereco).where(*filtros)
        )
        enderecos = await self._session.scalars(
            select(Endereco)
            .where(*filtros)
            .order_by(Endereco.id)
            .limit(limit)
            .offset(offset)
        )
        return enderecos.all(), total

    async def remover(self, cep: str) -> bool:
        stmt = delete(Endereco).where(Endereco.cep == normalizar_cep(cep))
        resultado = await self._session.execute(stmt)
        await self._session.commit()
        return resultado.rowcount > 0
