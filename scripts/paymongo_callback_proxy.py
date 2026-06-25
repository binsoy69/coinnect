"""Expose only Coinnect's PayMongo callback routes to a public tunnel."""

from __future__ import annotations

import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8020
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
ALLOWED_PATHS = {
    "/api/v1/ewallet/webhook",
    "/api/v1/ewallet/transfer-callback",
}
FORWARDED_HEADERS = {
    "content-type",
    "paymongo-signature",
    "x-paymongo-signature",
}


class CallbackProxyHandler(BaseHTTPRequestHandler):
    server_version = "CoinnectCallbackProxy/1.0"

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in ALLOWED_PATHS:
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        body = self.rfile.read(content_length)
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() in FORWARDED_HEADERS
        }
        headers["Content-Length"] = str(len(body))

        connection = http.client.HTTPConnection(
            BACKEND_HOST,
            BACKEND_PORT,
            timeout=30,
        )
        try:
            connection.request("POST", path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()
        except OSError:
            self.send_error(502, "Coinnect backend unavailable")
            return
        finally:
            connection.close()

        self.send_response(response.status)
        content_type = response.getheader("Content-Type")
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self) -> None:
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        # Avoid persisting callback payloads or authorization information.
        print(f"{self.client_address[0]} {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        (LISTEN_HOST, LISTEN_PORT),
        CallbackProxyHandler,
    )
    print(
        f"PayMongo callback proxy listening on "
        f"http://{LISTEN_HOST}:{LISTEN_PORT}"
    )
    server.serve_forever()
