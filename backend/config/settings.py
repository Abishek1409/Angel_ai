import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Allow Railway, Vercel, and Render domains automatically
ALLOWED_HOSTS += [".railway.app", ".vercel.app", ".onrender.com"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "documents",
    "chat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql" if os.environ.get("DATABASE_URL") else "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Use PostgreSQL if DATABASE_URL is set (production), otherwise SQLite
if "DATABASE_URL" in os.environ:
    import dj_database_url
    DATABASES["default"] = dj_database_url.config(conn_max_age=600)
else:
    # SQLite fallback - create directory if needed
    db_path = BASE_DIR / "db.sqlite3"
    db_path.parent.mkdir(exist_ok=True)
    DATABASES["default"]["NAME"] = db_path

STATIC_URL = "/static/"

# Media files (uploaded documents)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# CORS — strip any trailing slashes from origins
CORS_ALLOWED_ORIGINS = [
    o.rstrip("/")
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:4200").split(",")
    if o.strip()
]

# Allow all Vercel preview deployments automatically
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

# Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "documents": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "chat": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
