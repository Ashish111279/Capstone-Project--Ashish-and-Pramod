import unittest

from app import main


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        with main._metrics_lock:
            main._request_counts.clear()

    def request(self, path="/", method="GET"):
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        environ = {"REQUEST_METHOD": method, "PATH_INFO": path}
        body = b"".join(main.application(environ, start_response))
        return captured["status"], captured["headers"], body

    def test_root_serves_application_page(self):
        status, headers, body = self.request()
        self.assertEqual(status, "200 OK")
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Capstone service", body)

    def test_health_and_readiness_are_ok(self):
        for path in ("/healthz", "/readyz"):
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, "200 OK")
                self.assertEqual(body, b'{"status":"ok"}')

    def test_metrics_exposes_prometheus_counter(self):
        self.request("/healthz")
        status, headers, body = self.request("/metrics")
        self.assertEqual(status, "200 OK")
        self.assertIn("text/plain", headers["Content-Type"])
        self.assertIn(b'app_http_requests_total{method="GET",path="/healthz",status="200"} 1', body)

    def test_unknown_path_and_non_get_method_are_rejected(self):
        self.assertEqual(self.request("/missing")[0], "404 Not Found")
        self.assertEqual(self.request("/", "POST")[0], "405 Method Not Allowed")
        _, _, metrics = self.request("/metrics")
        self.assertIn(b'method="OTHER"', metrics)


if __name__ == "__main__":
    unittest.main()