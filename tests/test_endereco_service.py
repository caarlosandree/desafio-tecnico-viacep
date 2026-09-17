import pytest

from app.clients.exceptions import CepInvalidoError, CepNaoEncontradoError
from app.services.endereco_service import EnderecoService
from tests.fakes import COPACABANA, PAULISTA, SE

pytestmark = pytest.mark.anyio


@pytest.fixture
def service(session, viacep) -> EnderecoService:
    return EnderecoService(session, viacep)


async def importar_todos(service: EnderecoService) -> None:
    for cep in (SE.cep, PAULISTA.cep, COPACABANA.cep):
        await service.importar(cep)


async def test_importar_salva_endereco(service):
    endereco, criado = await service.importar("01001-000")

    assert criado is True
    assert endereco.id is not None
    assert endereco.cep == "01001000"
    assert endereco.logradouro == "Praça da Sé"
    assert endereco.uf == "SP"
    assert endereco.created_at is not None
    assert endereco.updated_at is not None


async def test_importar_mesmo_cep_nao_duplica(service):
    primeiro, _ = await service.importar("01001000")
    segundo, criado = await service.importar("01001-000")

    assert criado is False
    _, total = await service.listar()
    assert total == 1
    assert segundo.id == primeiro.id


async def test_importar_novamente_atualiza_dados(service, viacep):
    original, _ = await service.importar(SE.cep)

    viacep.enderecos[SE.cep] = SE.model_copy(
        update={"logradouro": "Praça da Sé (novo)"}
    )
    atualizado, criado = await service.importar(SE.cep)

    assert criado is False

    assert atualizado.id == original.id
    assert atualizado.logradouro == "Praça da Sé (novo)"


async def test_importar_novamente_preserva_created_at(service):
    original, _ = await service.importar(SE.cep)
    criado_em = original.created_at

    atualizado, criado = await service.importar(SE.cep)

    assert criado is False
    # O UPDATE mexe só nos campos vindos do ViaCEP e no updated_at.
    assert atualizado.created_at == criado_em


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
