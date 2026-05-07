# jump-storage

Abstração de storage de arquivos compartilhada entre backend (FastAPI) e worker (Python).

## Backends

| Backend | Quando usar | Dependências |
|---|---|---|
| `local` | dev, CI, ambientes sem credenciais R2 | nenhuma extra |
| `r2` | produção (Cloudflare R2 — S3-compatible) | `boto3` |

Seleção via env `OBJECT_STORAGE_BACKEND=local|r2`.

## API

```python
from jump_storage import get_storage

storage = get_storage()  # lê env

key = storage.put(content_bytes, key="proposals/abc/v1.pdf", content_type="application/pdf")
url = storage.get_signed_url(key, ttl_seconds=300)  # 5 minutos
content = storage.get(key)
storage.delete(key)
storage.exists(key)  # bool
```

## Signed URLs

- **R2:** boto3 `generate_presigned_url`. URL externa com assinatura embutida.
- **Local:** URL apontando para `{LOCAL_STORAGE_BASE_URL}/files/signed/{token}/{key}`. O backend valida o token (HMAC do key + exp), serve o arquivo. TTL é configurável.

`get_signed_url` retorna sempre uma string URL — o consumidor não sabe qual backend está atrás.
