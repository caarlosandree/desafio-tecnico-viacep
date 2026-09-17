import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.dependencies import get_endereco_service
from app.clients.exceptions import ViaCepIndisponivelError
from app.core.config import get_settings
from app.core.security import API_KEY_HEADER
from app.db.session import get_session
from app.main import app
from app.services.endereco_service import EnderecoService
from tests.fakes import COPACABANA, PAULISTA, SE

pytestmark = pytest.mark.anyio

URL = "/api/v1/enderecos"
API_KEY_TESTE = "chave-de-teste"


@pytest.fixture
async def client(session, viacep):
    """Cliente HTTP que já envia a chave de API válida."""
    settings_teste = get_settings().model_copy(
        update={"api_key": SecretStr(API_KEY_TESTE)}
    )
    app.dependency_overrides[get_settings] = lambda: settings_teste
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_endereco_service] = lambda: EnderecoService(
        session, viacep
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={API_KEY_HEADER: API_KEY_TESTE},
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def importar_todos(client: AsyncClient) -> None:
    for cep in (SE.cep, PAULISTA.cep, COPACABANA.cep):
        response = await client.post(f"{URL}/{cep}")
        assert response.status_code == 201


# ---------- POST /enderecos/{cep} ----------


async def test_importar_retorna_201_com_endereco(client):
    response = await client.post(f"{URL}/01001-000")

    assert response.status_code == 201
    corpo = response.json()
    assert corpo["cep"] == "01001000"
    assert corpo["localidade"] == "São Paulo"
    assert corpo["uf"] == "SP"
    assert {"id", "created_at", "updated_at"} <= corpo.keys()


async def test_importar_mesmo_cep_nao_duplica(client):
    primeiro = await client.post(f"{URL}/{SE.cep}")
    segundo = await client.post(f"{URL}/{SE.cep}")

    assert segundo.status_code == 201
    assert segundo.json()["id"] == primeiro.json()["id"]
    assert (await client.get(URL)).json()["total"] == 1


async def test_importar_cep_inexistente_retorna_404(client):
    response = await client.post(f"{URL}/99999999")

    assert response.status_code == 404
    assert "não encontrado" in response.json()["detail"]


async def test_importar_cep_invalido_retorna_422(client):
    response = await client.post(f"{URL}/123")

    assert response.status_code == 422
    assert "CEP inválido" in response.json()["detail"]


async def test_importar_viacep_fora_do_ar_retorna_502(client, viacep):
    viacep.erro = ViaCepIndisponivelError("tempo de resposta excedido")

    response = await client.post(f"{URL}/{SE.cep}")

    assert response.status_code == 502
    assert "ViaCEP" in response.json()["detail"]


# ---------- GET /enderecos ----------


async def test_listar_vazio(client):
    response = await client.get(URL)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_listar_filtra_por_uf(client):
    await importar_todos(client)

    response = await client.get(URL, params={"uf": "rj"})

    corpo = response.json()
    assert corpo["total"] == 1
    assert corpo["items"][0]["cep"] == COPACABANA.cep


async def test_listar_filtra_por_localidade(client):
    await importar_todos(client)

    response = await client.get(URL, params={"localidade": "paulo"})

    assert response.json()["total"] == 2


async def test_listar_paginado(client):
    await importar_todos(client)

    response = await client.get(URL, params={"limit": 1, "offset": 1})

    corpo = response.json()
    assert corpo["total"] == 3
    assert [item["cep"] for item in corpo["items"]] == [PAULISTA.cep]


@pytest.mark.parametrize(
    "params",
    [{"uf": "XYZ"}, {"uf": "1A"}, {"limit": 0}, {"limit": 101}, {"offset": -1}],
)
async def test_listar_parametros_invalidos_retornam_422(client, params):
    response = await client.get(URL, params=params)

    assert response.status_code == 422


# ---------- GET /enderecos/{cep} ----------


async def test_obter_endereco_salvo(client):
    await client.post(f"{URL}/{SE.cep}")

    response = await client.get(f"{URL}/01001-000")

    assert response.status_code == 200
    assert response.json()["logradouro"] == "Praça da Sé"


async def test_obter_cep_nao_salvo_retorna_404_sem_chamar_viacep(client, viacep):
    response = await client.get(f"{URL}/{SE.cep}")

    assert response.status_code == 404
    assert viacep.chamadas == 0


async def test_obter_cep_invalido_retorna_422(client):
    response = await client.get(f"{URL}/abc")

    assert response.status_code == 422


# ---------- DELETE /enderecos/{cep} ----------


async def test_remover_endereco(client):
    await client.post(f"{URL}/{SE.cep}")

    primeira = await client.delete(f"{URL}/{SE.cep}")
    segunda = await client.delete(f"{URL}/{SE.cep}")

    assert primeira.status_code == 204
    assert primeira.content == b""
    assert segunda.status_code == 404


# ---------- Autenticação ----------

ROTAS_PROTEGIDAS = [
    ("post", f"{URL}/{SE.cep}"),
    ("get", URL),
    ("get", f"{URL}/{SE.cep}"),
    ("delete", f"{URL}/{SE.cep}"),
]


@pytest.mark.parametrize(("metodo", "rota"), ROTAS_PROTEGIDAS)
async def test_rotas_sem_chave_retornam_401(client, viacep, metodo, rota):
    del client.headers[API_KEY_HEADER]

    response = await client.request(metodo, rota)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "ApiKey"
    assert response.json() == {"detail": "Chave de API ausente ou inválida."}
    assert viacep.chamadas == 0


@pytest.mark.parametrize("chave", ["errada", "", API_KEY_TESTE.upper()])
async def test_chave_invalida_retorna_401(client, chave):
    client.headers[API_KEY_HEADER] = chave

    response = await client.get(URL)

    assert response.status_code == 401


async def test_health_nao_exige_chave(client):
    del client.headers[API_KEY_HEADER]

    response = await client.get("/health")

    assert response.status_code == 200


async def test_openapi_documenta_autenticacao(client):
    spec = (await client.get("/openapi.json")).json()

    esquema = spec["components"]["securitySchemes"]["APIKeyHeader"]
    assert esquema == {
        "type": "apiKey",
        "in": "header",
        "name": API_KEY_HEADER,
        "description": "Chave de acesso definida na variável de ambiente `API_KEY`.",
    }
    assert spec["paths"][URL]["get"]["security"] == [{"APIKeyHeader": []}]
    assert "security" not in spec["paths"]["/health"]["get"]


# ---------- Health e documentação ----------


async def test_health(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "banco": "ok"}


async def test_openapi_documenta_rotas(client):
    paths = (await client.get("/openapi.json")).json()["paths"]

    assert set(paths[URL]) == {"get"}
    assert set(paths[f"{URL}/{{cep}}"]) == {"post", "get", "delete"}
    assert "/health" in paths
