"""Fast, isolated settings for the compliance API test suite."""

import tempfile

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("OPSBRIDGE_SQLITE_PATH", ":memory:"),
    }
}
_TEST_MEDIA = tempfile.TemporaryDirectory(prefix="opsbridge-compliance-tests-")
MEDIA_ROOT = _TEST_MEDIA.name
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = os.getenv("OPSBRIDGE_EAGER_TASKS", "false").lower() == "true"
CELERY_TASK_EAGER_PROPAGATES = True
