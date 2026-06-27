# Security & Code Review — RAG Template

> Gerado em: 2026-06-27
> Base de análise: Sessões 1–4 (src/auth.py, src/models.py, src/config/, src/database.py, tests/)

---

## Legenda

| Símbolo | Significado |
|---------|-------------|
| 🔴 | Alta — risco real em produção |
| 🟡 | Média — fragilidade ou vetor de ataque em condições específicas |
| 🟢 | Baixa — má prática, mas sem risco imediato |
| ⚪ | Info — limpeza ou consistência |

---

## 🔴 Alta

### 1. Secret key JWT com fallback público
**Arquivo:** `src/auth.py:17`

```python
# atual — inseguro
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
```

**Problema:** Se `JWT_SECRET_KEY` não estiver setado, a aplicação sobe normalmente com um secret conhecido e público. Qualquer pessoa pode assinar tokens válidos offline.

**Correção:**
```python
# correto — crasha no boot se não configurado
SECRET_KEY = os.environ["JWT_SECRET_KEY"]
```

**Status:** ✅ concluído

---

### 2. Cookies sem `secure=True` e sem `max_age`
**Arquivo:** `src/auth.py:60-61` e `src/auth.py:134`

```python
# atual — sem secure, sem expiração
response.set_cookie("access_token", access_token, httponly=True, samesite="lax")
response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax")
```

**Problemas:**
- Sem `secure=True`: o cookie trafega em HTTP — interceptável por MITM.
- Sem `max_age`: o refresh_token vira session cookie (some ao fechar o browser), mas o JWT permanece válido por 7 dias. Inconsistência entre vida do token e vida do cookie.

**Correção:**
```python
response.set_cookie(
    "access_token", access_token,
    httponly=True, samesite="lax", secure=True,
    max_age=int(ACCESS_TOKEN_EXPIRE.total_seconds()),
)
response.set_cookie(
    "refresh_token", refresh_token,
    httponly=True, samesite="lax", secure=True,
    max_age=int(REFRESH_TOKEN_EXPIRE.total_seconds()),
)
```

> Nota: `secure=True` bloqueia cookies em HTTP puro. Em desenvolvimento local (HTTP), usar flag condicional via env var: `secure = os.environ.get("ENV") != "development"`.

**Status:** ⬜ pendente

---

## 🟡 Média

### 3. Access token e refresh token indistinguíveis
**Arquivo:** `src/auth.py:38-45`

```python
# os dois têm estrutura idêntica — só exp muda
def create_access_token(user_id: str, ...) -> str:
    return jwt.encode({"sub": user_id, "exp": expire}, ...)

def create_refresh_token(user_id: str, ...) -> str:
    return jwt.encode({"sub": user_id, "exp": expire}, ...)
```

**Problema:** Um refresh token submetido como access token (ou vice-versa) é aceito pelo servidor. O endpoint `/refresh` deveria rejeitar um access token.

**Correção:** Adicionar claim `typ` e validar no decode:
```python
# geração
{"sub": user_id, "exp": expire, "typ": "access"}   # ou "refresh"

# validação
def _decode_token(token: str, expected_typ: str) -> str:
    payload = jwt.decode(...)
    if payload.get("typ") != expected_typ:
        raise HTTPException(status_code=401, detail="token inválido")
```

**Status:** ⬜ pendente

---

### 4. Sem rotação do refresh token
**Arquivo:** `src/auth.py:117-135`

**Problema:** O endpoint `/refresh` emite novo access token mas mantém o mesmo refresh token indefinidamente. Refresh token rotation é o mecanismo que detecta roubo: se o mesmo refresh token for usado duas vezes (usuário legítimo + atacante), o servidor detecta a anomalia.

**Correção:** A cada `/refresh`, emitir também um novo refresh token e devolvê-lo no cookie.

```python
# no endpoint /refresh
new_access = create_access_token(str(user.id))
new_refresh = create_refresh_token(str(user.id))
_set_auth_cookies(response, new_access, new_refresh)
```

**Status:** ⬜ pendente

---

### 5. Cookie do `/refresh` ignora o helper `_set_auth_cookies`
**Arquivo:** `src/auth.py:134`

```python
# atual — chama set_cookie diretamente
response.set_cookie("access_token", access_token, httponly=True, samesite="lax")
```

**Problema:** Quando `_set_auth_cookies` for atualizado (ex: adicionar `secure=True`, `max_age`), o `/refresh` fica desatualizado silenciosamente.

**Correção:** Usar o helper em todos os lugares onde cookies são setados.

**Status:** ⬜ pendente

---

### 6. `PipelineVersion.status` sem constraint de banco
**Arquivo:** `src/models.py:55`

```python
status: Mapped[str] = mapped_column(String, nullable=False)
```

**Problema:** `status="banana"` é inserido sem erro. Os valores válidos (`active`, `staging`, `archived`, `deleted`) existem apenas na documentação — o banco não os conhece.

**Correção (opção A — CheckConstraint):**
```python
from sqlalchemy import CheckConstraint

__table_args__ = (
    CheckConstraint(
        "status IN ('active', 'staging', 'archived', 'deleted')",
        name="ck_pipeline_version_status",
    ),
)
```

**Correção (opção B — Python Enum + migration):**
```python
import enum

class VersionStatus(str, enum.Enum):
    active = "active"
    staging = "staging"
    archived = "archived"
    deleted = "deleted"

status: Mapped[VersionStatus] = mapped_column(String, nullable=False)
```

**Status:** ⬜ pendente

---

## 🟢 Baixa

### 7. Lazy imports dentro de route handlers
**Arquivo:** `src/auth.py:98, 122, 141`

```python
def login(...):
    from fastapi.responses import JSONResponse  # import dentro da função
```

**Problema:** `JSONResponse` é importado em três handlers separados a cada request. Obscurece dependências e é incomum — futuros leitores vão se perguntar por que está ali.

**Correção:** Mover para o topo do arquivo com os outros imports.

**Status:** ⬜ pendente

---

### 8. Duas funções idênticas para criar tokens
**Arquivo:** `src/auth.py:38-45`

```python
def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (expires_delta or ACCESS_TOKEN_EXPIRE)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (expires_delta or REFRESH_TOKEN_EXPIRE)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
```

**Problema:** Lógica duplicada. Se o algoritmo mudar, muda em dois lugares.

**Correção:** Unificar (resolve também o item 3):
```python
def _create_token(user_id: str, typ: str, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    return jwt.encode({"sub": user_id, "exp": expire, "typ": typ}, SECRET_KEY, algorithm=ALGORITHM)

def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    return _create_token(user_id, "access", expires_delta or ACCESS_TOKEN_EXPIRE)

def create_refresh_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    return _create_token(user_id, "refresh", expires_delta or REFRESH_TOKEN_EXPIRE)
```

**Status:** ⬜ pendente

---

### 9. `DATABASE_URL` crashando no import
**Arquivo:** `src/database.py:7`

```python
DATABASE_URL = os.environ["DATABASE_URL"]  # executa no import
```

**Problema:** Qualquer `import` de `src.database` (mesmo em testes unitários sem banco) explode com `KeyError` se a env var não estiver setada. O `conftest.py` contorna isso com `os.environ.setdefault` no topo — workaround frágil dependente de ordem de import.

**Alternativa considerada:** Mover para função lazy ou usar `os.environ.get` com erro explícito no `create_engine`. Discutir antes de agir — mudança afeta o conftest.

**Status:** ⬜ pendente

---

### 10. Testes acessando internal do slowapi
**Arquivo:** `tests/test_auth.py:39`

```python
limiter._limiter.storage.reset()
```

**Problema:** `_limiter` e `storage` são atributos privados. Uma atualização do slowapi pode renomeá-los e quebrar todos os testes de auth silenciosamente.

**Alternativa:** Mockar o decorator de rate limit via `pytest.mark` ou configurar o limiter com storage injetável por env var nos testes.

**Status:** ⬜ pendente

---

### 11. Testes usam `create_all` em vez de migrations Alembic
**Arquivo:** `tests/conftest.py:20`

```python
Base.metadata.create_all(eng)
```

**Problema:** O schema dos testes vem dos models Python, não das migrations. Se uma migration adicionar um index, trigger, default SQL, ou constraint que não esteja nos models, os testes nunca o verão. Schema de produção e schema de testes podem divergir silenciosamente.

**Alternativa:** Rodar `alembic upgrade head` no setup do `engine` fixture, apontando para o banco de teste.

**Observação:** Mudança tem impacto no `conftest.py` e precisa do Alembic configurado para apontar ao banco de teste.

**Status:** ⬜ pendente

---

## ⚪ Info

### 12. `pydantic-settings` instalado mas não usado
**Arquivo:** `pyproject.toml`

O `src/config/loader.py` usa `os.environ` diretamente. `pydantic-settings` está nas dependências mas não contribui com nada.

**Opções:**
- Remover a dependência (mais simples, YAGNI).
- Migrar o loader para `pydantic-settings` e aproveitar a validação automática de env vars.

**Status:** ⬜ pendente

---

### 13. Dimensão 768 implicitamente acoplada ao modelo Nomic
**Arquivo:** `src/models.py:110`

```python
embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
```

Não é um bug agora, mas se o embedder mudar para um modelo com outra dimensão (ex: OpenAI 1536), a inserção falha com erro opaco do pgvector.

**Sugestão:** Documentar a dependência explicitamente como comentário na migration ou no CLAUDE.md, e registrar como item a endereçar na sessão de embedders (S6).

**Status:** ⚪ aceito por ora — revisar na Sessão 6

---

## Progresso geral

| Item | Severidade | Status |
|------|-----------|--------|
| 1. Secret key com fallback público | 🔴 Alta | ✅ |
| 2. Cookies sem `secure` e sem `max_age` | 🔴 Alta | ⬜ |
| 3. Tokens access/refresh indistinguíveis | 🟡 Média | ⬜ |
| 4. Sem rotação do refresh token | 🟡 Média | ⬜ |
| 5. `/refresh` ignora helper de cookie | 🟡 Média | ⬜ |
| 6. `status` sem constraint de banco | 🟡 Média | ⬜ |
| 7. Lazy imports dentro de handlers | 🟢 Baixa | ⬜ |
| 8. Funções `create_*_token` duplicadas | 🟢 Baixa | ⬜ |
| 9. `DATABASE_URL` crashando no import | 🟢 Baixa | ⬜ |
| 10. Testes acessam internal do slowapi | 🟢 Baixa | ⬜ |
| 11. `create_all` vs migrations em testes | 🟢 Baixa | ⬜ |
| 12. `pydantic-settings` morto | ⚪ Info | ⬜ |
| 13. Dimensão 768 acoplada ao Nomic | ⚪ Info | ⬜ |
