import threading

_request_local = threading.local()


def get_current_request():
    return getattr(_request_local, 'request', None)


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AuditMiddleware:
    """
    Middleware d'audit — hérité de DSI Diligences.
    Stocke la requête courante dans un thread-local pour que les signals
    puissent accéder à l'IP et au user-agent sans les passer explicitement.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _request_local.request = request
        try:
            response = self.get_response(request)
        finally:
            _request_local.request = None
        return response
