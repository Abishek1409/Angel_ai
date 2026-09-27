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
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
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
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Gemini API (for embeddings - free tier available)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_EMBEDDING_MODEL = os.environ.get(
    "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
)

# Gemini API (used for embeddings and chat)
GEMINI_CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash")

# Groq API (primary LLM provider for chat generation)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# OpenRouter API (fallback LLM provider with multiple free models)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_FREE_MODELS = [
    model.strip()
    for model in os.environ.get(
        "OPENROUTER_FREE_MODELS",
        "meta-llama/llama-3.1-8b-instruct:free,"
        "qwen/qwen-2.5-7b-instruct:free,"
        "mistralai/mistral-7b-instruct:free,"
        "x-ai/grok-beta:free"
    ).split(",")
    if model.strip()
]

# Redis cache
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Production security settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

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
