from .correlation import resolve_correlation_id
from .tracing import tag_current_span


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.correlation_id = resolve_correlation_id(request.headers.get("X-Correlation-Id"))
        tag_current_span(request.correlation_id)
        response = self.get_response(request)
        response["X-Correlation-Id"] = request.correlation_id
        return response
