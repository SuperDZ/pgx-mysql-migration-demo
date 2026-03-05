from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "demo-secret-key-not-for-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "banktel.apps.BanktelConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "demo_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "demo_project.wsgi.application"
ASGI_APPLICATION = "demo_project.asgi.application"

DB_TARGET = os.getenv("DB_TARGET", "mysql").strip().lower()

if DB_TARGET == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("MYSQL_DB", "demo"),
            "HOST": os.getenv("MYSQL_HOST", "192.168.31.15"),
            "PORT": int(os.getenv("MYSQL_PORT", "3306")),
            "USER": os.getenv("MYSQL_USER", "root"),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
        }
    }
elif DB_TARGET == "pgx":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("PGX_DB", "demo"),
            "HOST": os.getenv("PGX_HOST", "192.168.31.10"),
            "PORT": int(os.getenv("PGX_PORT", "5432")),
            "USER": os.getenv("PGX_USER", "postgresql"),
            "PASSWORD": os.getenv("PGX_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
        }
    }
elif DB_TARGET == "pg":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("PG_DB", "demo"),
            "HOST": os.getenv("PG_HOST", "192.168.31.20"),
            "PORT": int(os.getenv("PG_PORT", "5432")),
            "USER": os.getenv("PG_USER", "postgresql"),
            "PASSWORD": os.getenv("PG_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    raise ValueError("DB_TARGET must be one of: mysql, pgx, pg")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOG_DIR = BASE_DIR / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        }
    },
    "handlers": {
        "app_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(LOG_DIR / "app.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
        "bootstrap_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(LOG_DIR / "bootstrap.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
        "sql_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(LOG_DIR / "sql.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
        "access_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(LOG_DIR / "access.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["app_file"],
        "level": "INFO",
    },
    "loggers": {
        "banktel": {
            "handlers": ["app_file"],
            "level": "INFO",
            "propagate": False,
        },
        "bootstrap": {
            "handlers": ["bootstrap_file"],
            "level": "INFO",
            "propagate": False,
        },
        "sql": {
            "handlers": ["sql_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["access_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["access_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
