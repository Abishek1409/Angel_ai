import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    """Health check endpoint for uptime ping services. No DB or API calls."""
    return JsonResponse({"status": "healthy"}, status=200)


def db_health_check(request):
    """
    Health check that runs a tiny query, for an uptime monitor.

    Pinging this regularly keeps the free Supabase project active so it isn't
    paused for inactivity, and returns 503 when the database is unreachable so
    the monitor alerts. Render's own health check should stay on /health/, so a
    database outage doesn't make Render restart the web service.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Database health check failed")
        return JsonResponse({"status": "unhealthy", "database": "unreachable"}, status=503)
    return JsonResponse({"status": "healthy", "database": "ok"}, status=200)
