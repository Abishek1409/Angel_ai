import os

import chromadb
from chromadb.config import Settings
from django.conf import settings


_CHROMA_PATH = os.path.join(settings.BASE_DIR, "chroma_db")


def get_chroma_client():
    """Create a local Chroma client with telemetry disabled explicitly."""
    return chromadb.PersistentClient(
        path=_CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )
