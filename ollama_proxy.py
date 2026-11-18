import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import requests


MAX_REQUEST_BYTES = 10 * 1024 * 1024
UPSTREAM_URL = "http://127.0.0.1:11434"


class OllamaProxyHandler(BaseHTTPRequestHandler):
    server_version = "OllamaProxy"
    sys_version = ""

    def do_GET(self):
        self._proxy_request("GET")

    def do_POST(self):
        self._proxy_request("POST")

    def _proxy_request(self, method):
        parsed_path = urlsplit(self.path)
        allowed_paths = {
            "GET": {"/api/tags"},
            "POST": {"/api/chat"},
        }
        if (
            parsed_path.path not in allowed_paths[method]
            or parsed_path.query
            or parsed_path.fragment
        ):
            self._send_json(404, {"error": "Not found"})
            return

        token = os.environ.get("OLLAMA_PROXY_TOKEN", "")
        if not token or len(token) < 32:
            self._send_json(503, {"error": "Proxy authentication is not configured"})
            return
        expected = f"Bearer {token}"
        provided = self.headers.get("Authorization", "")
        if not hmac.compare_digest(provided, expected):
            self._send_json(401, {"error": "Unauthorized"})
            return

        body = None
        headers = {}
        timeout = 5
        if method == "POST":
            content_type = self.headers.get("Content-Type", "")
            if content_type.split(";", 1)[0].strip().lower() != "application/json":
                self._send_json(415, {"error": "Content-Type must be application/json"})
                return
            try:
                body_size = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send_json(411, {"error": "Content-Length is required"})
                return
            if body_size < 0 or body_size > MAX_REQUEST_BYTES:
                self._send_json(413, {"error": "Request body is too large"})
                return
            body = self.rfile.read(body_size)
            if len(body) != body_size:
                self._send_json(400, {"error": "Request body is incomplete"})
                return
            headers["Content-Type"] = "application/json"
            timeout = 300

        try:
            if method == "GET":
                response = requests.get(
                    f"{UPSTREAM_URL}{parsed_path.path}",
                    timeout=timeout,
                )
            else:
                response = requests.post(
                    f"{UPSTREAM_URL}{parsed_path.path}",
                    data=body,
                    headers=headers,
                    timeout=timeout,
                )
        except requests.RequestException:
            self._send_json(502, {"error": "Ollama upstream is unavailable"})
            return

        response_body = response.content
        self.send_response(response.status_code)
        self.send_header(
            "Content-Type",
            response.headers.get("Content-Type", "application/json"),
        )
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class OllamaProxyServer(ThreadingHTTPServer):
    daemon_threads = True


def main():
    token = os.environ.get("OLLAMA_PROXY_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("Set OLLAMA_PROXY_TOKEN to a random value of at least 32 characters.")

    server = OllamaProxyServer(("127.0.0.1", 11435), OllamaProxyHandler)
    print("Authenticated Ollama proxy listening on http://127.0.0.1:11435")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
