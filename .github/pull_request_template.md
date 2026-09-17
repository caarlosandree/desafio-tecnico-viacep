## O que muda

<!-- Descreva a alteração e o motivo. -->

## Como testar

<!-- Passos para validar a mudança. -->

## Checklist

- [ ] `ruff check .` e `ruff format --check .` sem erros
- [ ] `pytest` passando (com o banco de pé: `docker compose up -d --wait db`)
- [ ] Migration criada e revisada, se o modelo de dados mudou
- [ ] README / collection do Postman atualizados, se a API mudou
- [ ] Nenhum segredo (`.env`, chaves) incluído
