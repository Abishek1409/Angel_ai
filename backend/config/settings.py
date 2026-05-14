import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Allow Railway and Vercel domains automatically
ALLOWED_HOSTS += [".railway.app", ".vercel.app"]

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
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

STATIC_URL = "/static/"

# Media files (uploaded documents)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:4200"
).split(",")

# Allow all Vercel preview deployments automatically
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

# Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
