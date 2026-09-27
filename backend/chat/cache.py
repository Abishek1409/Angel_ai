import hashlib
import json
import logging
import redis
from django.conf import settings
from typing import Optional

logger = logging.getLogger(__name__)


def _get_redis_client():
    """Get Redis client, returns None if Redis is not available."""
    try:
        redis_url = settings.REDIS_URL
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()  # Test connection
        logger.info(f"✓ Redis connected successfully at {redis_url}")
        return client
    except Exception as e:
        logger.warning(f"✗ Redis not available ({type(e).__name__}: {str(e)}), continuing without cache")
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
            logger.info("✓ Cache HIT: embedding retrieved from Redis")
            return json.loads(cached)
        logger.debug("✗ Cache MISS: embedding not found in Redis")
    except Exception as e:
        logger.warning(f"Redis get_cached_embedding error: {e}")
    
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
        logger.info(f"✓ Cached embedding to Redis (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Redis cache_embedding error: {e}")


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
            logger.info("✓ Cache HIT: response retrieved from Redis")
            return data["answer"], data["sources"], data.get("citations", [])
        logger.debug("✗ Cache MISS: response not found in Redis")
    except Exception as e:
        logger.warning(f"Redis get_cached_response error: {e}")

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
        logger.info(f"✓ Cached response to Redis (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Redis cache_response error: {e}")
