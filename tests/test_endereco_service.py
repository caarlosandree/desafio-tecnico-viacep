import pytest

from app.clients.exceptions import CepInvalidoError, CepNaoEncontradoError
from app.clients.viacep import normalizar_cep
from app.schemas.viacep import ViaCepResponse
from app.services.endereco_service import EnderecoService

pytestmark = pytest.mark.anyio

SE = ViaCepResponse(
    cep="01001000",
    logradouro="Praça da Sé",
    bairro="Sé",
    localidade="São Paulo",
    uf="SP",
    ibge="3550308",
    ddd="11",
)
PAULISTA = ViaCepResponse(
    cep="01310100",
    logradouro="Avenida Paulista",
    bairro="Bela Vista",
    localidade="São Paulo",
    uf="SP",
    ibge="3550308",
    ddd="11",
)
COPACABANA = ViaCepResponse(
    cep="22070002",
    logradouro="Avenida Atlântica",
    bairro="Copacabana",
    localidade="Rio de Janeiro",
    uf="RJ",
    ibge="3304557",
    ddd="21",
)


class ViaCepFake:
    """Substitui o ViaCepClient, respondendo a partir de um dicionário."""

    def __init__(self, *enderecos: ViaCepResponse) -> None:
        self.enderecos = {endereco.cep: endereco for endereco in enderecos}
        self.chamadas = 0

    async def buscar(self, cep: str) -> ViaCepResponse:
        self.chamadas += 1
        cep = normalizar_cep(cep)
        if cep not in self.enderecos:
            raise CepNaoEncontradoError(cep)
        return self.enderecos[cep]


@pytest.fixture
def viacep() -> ViaCepFake:
    return ViaCepFake(SE, PAULISTA, COPACABANA)


@pytest.fixture
def service(session, viacep) -> EnderecoService:
    return EnderecoService(session, viacep)


async def importar_todos(service: EnderecoService) -> None:
    for cep in (SE.cep, PAULISTA.cep, COPACABANA.cep):
        await service.importar(cep)


async def test_importar_salva_endereco(service):
    endereco = await service.importar("01001-000")

    assert endereco.id is not None
    assert endereco.cep == "01001000"
    assert endereco.logradouro == "Praça da Sé"
    assert endereco.uf == "SP"
    assert endereco.created_at is not None
    assert endereco.updated_at is not None


async def test_importar_mesmo_cep_nao_duplica(service):
    primeiro = await service.importar("01001000")
    segundo = await service.importar("01001-000")

    _, total = await service.listar()
    assert total == 1
    assert segundo.id == primeiro.id


async def test_importar_novamente_atualiza_dados(service, viacep):
    original = await service.importar(SE.cep)

    viacep.enderecos[SE.cep] = SE.model_copy(
        update={"logradouro": "Praça da Sé (novo)"}
    )
    atualizado = await service.importar(SE.cep)

    assert atualizado.id == original.id
    assert atualizado.logradouro == "Praça da Sé (novo)"


async def test_importar_cep_inexistente_nao_salva(service):
    with pytest.raises(CepNaoEncontradoError):
        await service.importar("99999999")

    _, total = await service.listar()
    assert total == 0


async def test_obter_aceita_cep_com_hifen(service):
    await service.importar(SE.cep)

    endereco = await service.obter("01001-000")

    assert endereco is not None
    assert endereco.localidade == "São Paulo"


async def test_obter_cep_nao_salvo_retorna_none(service, viacep):
    assert await service.obter("01310100") is None
    assert viacep.chamadas == 0


async def test_obter_cep_invalido(service):
    with pytest.raises(CepInvalidoError):
        await service.obter("123")


async def test_listar_sem_filtros(service):
    await importar_todos(service)

    enderecos, total = await service.listar()

    assert total == 3
    assert [e.cep for e in enderecos] == [SE.cep, PAULISTA.cep, COPACABANA.cep]


async def test_listar_filtra_por_uf_sem_diferenciar_maiusculas(service):
    await importar_todos(service)

    enderecos, total = await service.listar(uf="rj")

    assert total == 1
    assert enderecos[0].cep == COPACABANA.cep


async def test_listar_filtra_por_parte_da_localidade(service):
    await importar_todos(service)

    enderecos, total = await service.listar(localidade="paulo")

    assert total == 2
    assert {e.cep for e in enderecos} == {SE.cep, PAULISTA.cep}


async def test_listar_localidade_trata_curinga_como_texto(service):
    await importar_todos(service)

    _, total = await service.listar(localidade="%")

    assert total == 0


async def test_listar_paginacao_mantem_total(service):
    await importar_todos(service)

    enderecos, total = await service.listar(limit=1, offset=1)

    assert total == 3
    assert [e.cep for e in enderecos] == [PAULISTA.cep]


async def test_remover(service):
    await service.importar(SE.cep)

    assert await service.remover("01001-000") is True
    assert await service.obter(SE.cep) is None
    assert await service.remover(SE.cep) is False
