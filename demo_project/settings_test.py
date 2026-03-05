from .settings import *  # noqa: F401,F403

DB_TARGET = "sqlite"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",
    }
}
