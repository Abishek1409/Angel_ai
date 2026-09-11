from django.http import JsonResponse


def health_check(request):
    """Health check endpoint for uptime ping services. No DB or API calls."""
    return JsonResponse({"status": "healthy"}, status=200)
