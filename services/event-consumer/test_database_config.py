import json
import unittest

from db_config import connection_kwargs


class DatabaseConfigTests(unittest.TestCase):
    def test_local_database_url_takes_precedence(self):
        self.assertEqual(
            connection_kwargs({"DATABASE_URL": "postgresql://local/example"}),
            {"conninfo": "postgresql://local/example"},
        )

    def test_aws_rds_secret_is_expanded_to_tls_connection_parameters(self):
        environment = {
            "APP_ENV": "production",
            "POSTGRES_DB": "opsbridge",
            "POSTGRES_MASTER_SECRET_JSON": json.dumps({
                "host": "db.internal",
                "port": 5432,
                "username": "runtime-user",
                "password": "synthetic-secret",
                "dbname": "master-name-ignored-by-config",
            }),
        }
        self.assertEqual(connection_kwargs(environment), {
            "host": "db.internal",
            "port": 5432,
            "dbname": "opsbridge",
            "user": "runtime-user",
            "password": "synthetic-secret",
            "sslmode": "require",
            "connect_timeout": 5,
        })

    def test_default_matches_local_compose_database(self):
        self.assertEqual(
            connection_kwargs({}),
            {"conninfo": "postgresql://opsbridge:opsbridge@localhost:5432/opsbridge"},
        )


if __name__ == "__main__":
    unittest.main()
