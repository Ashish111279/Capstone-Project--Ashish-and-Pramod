"""Small WSGI application with health endpoints and Prometheus metrics."""

from collections import Counter
from http import HTTPStatus
from threading import Lock
from wsgiref.simple_server import make_server
import os


_request_counts: Counter[tuple[str, str, int]] = Counter()
_metrics_lock = Lock()
_route_names = {"/": "/", "/healthz": "/healthz", "/readyz": "/readyz", "/metrics": "/metrics"}


def _response(status: HTTPStatus, content_type: str, body: bytes, start_response):
    start_response(
        f"{status.value} {status.phrase}",
        [("Content-Type", content_type), ("Content-Length", str(len(body)))],
    )
    return [body]


def application(environ, start_response):
    """Serve the app and expose request totals with bounded metric labels."""
    requested_method = environ.get("REQUEST_METHOD", "GET").upper()
    method = requested_method if requested_method == "GET" else "OTHER"
    path = environ.get("PATH_INFO", "/")
    route = _route_names.get(path, "/unknown")

    if requested_method != "GET":
        status = HTTPStatus.METHOD_NOT_ALLOWED
        content_type = "application/json; charset=utf-8"
        body = b'{"error":"method not allowed"}'
    elif path == "/":
        status = HTTPStatus.OK
        content_type = "text/html; charset=utf-8"
        body = (
            b"<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            b"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            b"<title>Capstone service</title><body><main><h1>Capstone service</h1>"
            b"<p>The application is running.</p></main></body></html>"
        )
    elif path in ("/healthz", "/readyz"):
        status = HTTPStatus.OK
        content_type = "application/json; charset=utf-8"
        body = b'{"status":"ok"}'
    elif path == "/metrics":
        status = HTTPStatus.OK
        content_type = "text/plain; version=0.0.4; charset=utf-8"
        with _metrics_lock:
            _request_counts[(method, route, status.value)] += 1
            metrics = [
                "# HELP app_http_requests_total Total HTTP requests handled.",
                "# TYPE app_http_requests_total counter",
            ]
            metrics.extend(
                f'app_http_requests_total{{method="{label_method}",path="{label_path}",status="{label_status}"}} {count}'
                for (label_method, label_path, label_status), count in sorted(_request_counts.items())
            )
        body = ("\n".join(metrics) + "\n").encode("utf-8")
        return _response(status, content_type, body, start_response)
    else:
        status = HTTPStatus.NOT_FOUND
        content_type = "application/json; charset=utf-8"
        body = b'{"error":"not found"}'

    with _metrics_lock:
        _request_counts[(method, route, status.value)] += 1
    return _response(status, content_type, body, start_response)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    with make_server("0.0.0.0", port, application) as server:
        print(f"Serving on port {port}", flush=True)
        server.serve_forever()