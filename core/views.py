from django.http import JsonResponse


def health_check(request):
    """Health check endpoint for load balancers and container orchestration."""
    return JsonResponse({"status": "healthy", "service": "app-api"})


def page_not_found(request, exception=None):
    return JsonResponse({"error": "Not found"}, status=404)
