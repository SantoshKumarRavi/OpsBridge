"""Build psycopg connection arguments from local URL or AWS RDS secret JSON."""
from __future__ import annotations

import json
from collections.abc import Mapping


def connection_kwargs(environment: Mapping[str, str]) -> dict[str, object]:
    database_url = environment.get("DATABASE_URL")
    if database_url:
        return {"conninfo": database_url}

    secret_json = environment.get("POSTGRES_MASTER_SECRET_JSON")
    if secret_json:
        secret = json.loads(secret_json)
        return {
            "host": secret["host"],
            "port": int(secret.get("port", 5432)),
            "dbname": environment.get("POSTGRES_DB", secret.get("dbname", "opsbridge")),
            "user": secret["username"],
            "password": secret["password"],
            "sslmode": "require" if environment.get("APP_ENV") == "production" else "prefer",
            "connect_timeout": 5,
        }

    return {"conninfo": "postgresql://opsbridge:opsbridge@localhost:5432/opsbridge"}
