"""Credential encryption — AES-256-GCM via libs/dbcore, key derived once at import time."""

from __future__ import annotations

from functools import lru_cache

from cryptography.exceptions import InvalidTag

from libs.dbcore import decrypt_secret, derive_key, encrypt_secret

from .config import get_settings


class VaultDecryptError(Exception):
    """Raised when a stored ciphertext can't be decrypted with the current key
    (typically ZA_VAULT_PASSWORD/ZA_VAULT_SALT were rotated without re-encrypting)."""


@lru_cache
def _key() -> bytes:
    settings = get_settings()
    return derive_key(settings.za_vault_password, settings.za_vault_salt)


def encrypt(plaintext: str) -> str:
    return encrypt_secret(plaintext, _key())


def decrypt(ciphertext: str) -> str:
    try:
        return decrypt_secret(ciphertext, _key())
    except (InvalidTag, ValueError) as exc:
        # Named, actionable failure instead of a bare 500 / stack trace.
        raise VaultDecryptError(
            "credential could not be decrypted — vault key mismatch. If "
            "ZA_VAULT_PASSWORD/ZA_VAULT_SALT were changed, re-encrypt existing "
            "rows with ops/rotate-vault-key.sh (using the OLD key)."
        ) from exc
