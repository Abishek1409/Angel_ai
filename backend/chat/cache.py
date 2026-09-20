import hashlib
import json
import redis
from django.conf import settings
from typing import Optional


def _get_redis_client():
    """Get Redis client, returns None if Redis is not available."""
    try:
        redis_url = settings.REDIS_URL
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()  # Test connection
        return client
    except Exception:
        # Redis not available, continue without caching
        return None


def _hash_key(text: str) -> str:
    """Generate SHA256 hash of text for use as cache key."""
    return hashlib.sha256(text.encode()).hexdigest()


def get_cached_embedding(query_text: str) -> Optional[list]:
    """
    Retrieve cached query embedding.
    
    Args:
        query_text: The raw query text.
        
    Returns:
        Cached embedding list or None if not found/Redis unavailable.
    """
    client = _get_redis_client()
    if not client:
        return None
    
    try:
        key = f"embedding:{_hash_key(query_text)}"
        cached = client.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    
    return None


def cache_embedding(query_text: str, embedding: list, ttl: int = 3600) -> None:
    """
    Cache query embedding.
    
    Args:
        query_text: The raw query text.
        embedding: The embedding vector.
        ttl: Time to live in seconds (default 1 hour).
    """
    client = _get_redis_client()
    if not client:
        return
    
    try:
        key = f"embedding:{_hash_key(query_text)}"
        client.setex(key, ttl, json.dumps(embedding))
    except Exception:
        pass


def get_cached_response(query_text: str, chunk_ids: list, cache_scope: str = "") -> Optional[tuple]:
    """
    Retrieve cached LLM response.

    Args:
        query_text: The raw query text.
        chunk_ids: List of chunk IDs that were retrieved.

    Returns:
        Tuple of (answer, sources, citations) or None if not found/Redis unavailable.
    """
    client = _get_redis_client()
    if not client:
        return None

    try:
        composite = cache_scope + "||" + query_text + "||" + "||".join(sorted(chunk_ids))
        key = f"response:{_hash_key(composite)}"
        cached = client.get(key)
        if cached:
            data = json.loads(cached)
            return data["answer"], data["sources"], data.get("citations", [])
    except Exception:
        pass

    return None


def cache_response(query_text: str, chunk_ids: list, answer: str, sources: list, citations: list, ttl: int = 3600, cache_scope: str = "") -> None:
    """
    Cache LLM response.

    Args:
        query_text: The raw query text.
        chunk_ids: List of chunk IDs that were retrieved.
        answer: The generated answer.
        sources: List of source filenames.
        citations: List of per-chunk citation dicts.
        ttl: Time to live in seconds (default 1 hour).
    """
    client = _get_redis_client()
    if not client:
        return

    try:
        composite = cache_scope + "||" + query_text + "||" + "||".join(sorted(chunk_ids))
        key = f"response:{_hash_key(composite)}"
        data = {"answer": answer, "sources": sources, "citations": citations}
        client.setex(key, ttl, json.dumps(data))
    except Exception:
        pass
