class ViaCepError(Exception):
    """Erro base para falhas na consulta ao ViaCEP."""


class CepInvalidoError(ViaCepError):
    def __init__(self, cep: str) -> None:
        self.cep = cep
        super().__init__(f"CEP inválido: {cep!r}. Informe 8 dígitos.")


class CepNaoEncontradoError(ViaCepError):
    def __init__(self, cep: str) -> None:
        self.cep = cep
        super().__init__(f"CEP {cep} não encontrado.")


class ViaCepIndisponivelError(ViaCepError):
    def __init__(self, motivo: str) -> None:
        super().__init__(f"Falha ao consultar o ViaCEP: {motivo}")