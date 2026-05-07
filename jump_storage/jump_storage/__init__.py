"""jump-storage — abstração de storage de arquivos (local | R2)."""

from .base import ObjectStorage, StorageError
from .factory import get_storage
from .local import LocalStorage, sign_local_url, verify_local_signature
from .r2 import R2Storage

__version__ = "0.1.0"

__all__ = [
    "LocalStorage",
    "ObjectStorage",
    "R2Storage",
    "StorageError",
    "get_storage",
    "sign_local_url",
    "verify_local_signature",
]
