from app.clients.exceptions import CepNaoEncontradoError
from app.clients.viacep import normalizar_cep
from app.schemas.viacep import ViaCepResponse

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
        self.erro: Exception | None = None

    async def buscar(self, cep: str) -> ViaCepResponse:
        self.chamadas += 1
        if self.erro is not None:
            raise self.erro
        cep = normalizar_cep(cep)
        if cep not in self.enderecos:
            raise CepNaoEncontradoError(cep)
        return self.enderecos[cep]
