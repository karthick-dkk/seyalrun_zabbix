#!/usr/bin/env python3
"""Re-encrypts every za_credentials.secret_ciphertext under a new
ZA_VAULT_PASSWORD/ZA_VAULT_SALT.

Invoked by ops/rotate-vault-key.sh inside the inventory-service container,
which already has libs/dbcore and its dependencies (cryptography,
SQLAlchemy, asyncpg/aiomysql) available.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import text

from libs.dbcore import build_database_url, decrypt_secret, derive_key, encrypt_secret, make_engine, make_sessionmaker


async def main() -> None:
    db_engine = os.environ["DB_ENGINE"]
    url = build_database_url(
        db_engine,
        os.environ["DB_USER"],
        os.environ["DB_PASSWORD"],
        os.environ["DB_HOST"],
        os.environ["DB_PORT"],
        os.environ["INVENTORY_DB_NAME"],
    )
    engine = make_engine(url, db_engine, os.environ.get("DB_SSLMODE", "require"))
    sessionmaker = make_sessionmaker(engine)

    old_key = derive_key(os.environ["OLD_ZA_VAULT_PASSWORD"], os.environ["OLD_ZA_VAULT_SALT"])
    new_key = derive_key(os.environ["ZA_VAULT_PASSWORD"], os.environ["ZA_VAULT_SALT"])

    async with sessionmaker() as session:
        rows = (await session.execute(text("SELECT id, secret_ciphertext FROM za_credentials"))).all()
        print(f"[*] Re-encrypting {len(rows)} credential(s)...")
        for row in rows:
            plaintext = decrypt_secret(row.secret_ciphertext, old_key)
            new_ciphertext = encrypt_secret(plaintext, new_key)
            await session.execute(
                text("UPDATE za_credentials SET secret_ciphertext = :ct WHERE id = :cred_id"),
                {"ct": new_ciphertext, "cred_id": row.id},
            )
        await session.commit()

    await engine.dispose()
    print("[OK] Vault key rotation complete.")


if __name__ == "__main__":
    asyncio.run(main())
