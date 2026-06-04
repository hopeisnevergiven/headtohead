from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote
import json
import requests


ALLOWED_HOSTS = {
    "www.ravenkog.com",
    "ravenkog.com",
}

TIMEOUT = 9

FORWARD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.ravenkog.com/",
    "Origin": "https://www.ravenkog.com",
    "Connection": "keep-alive",
}


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send(self, code, body: bytes, mime="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Requested-With",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _error(self, code, message, extra=None):
        payload = {
            "ok": False,
            "error": message,
        }

        if extra:
            payload.update(extra)

        self._json(code, payload)

    def do_OPTIONS(self):
        self._send(200, b"")

    def do_GET(self):
        try:
            parsed_request = urlparse(self.path)
            params = parse_qs(parsed_request.query)

            target_url = params.get("url", [""])[0]
            target_url = unquote(target_url).strip()

            if not target_url:
                return self._error(
                    400,
                    "Missing ?url= parameter",
                    {
                        "example": "/api/proxy?url=https%3A%2F%2Fwww.ravenkog.com%2Fapi%2Fmaps%2Flist"
                    },
                )

            parsed_target = urlparse(target_url)

            if parsed_target.scheme not in {"https", "http"}:
                return self._error(
                    400,
                    "Invalid URL scheme",
                    {"scheme": parsed_target.scheme},
                )

            if parsed_target.netloc not in ALLOWED_HOSTS:
                return self._error(
                    403,
                    "Host not allowed",
                    {
                        "host": parsed_target.netloc,
                        "allowed_hosts": sorted(ALLOWED_HOSTS),
                    },
                )

            response = requests.get(
                target_url,
                headers=FORWARD_HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True,
            )

            content_type = response.headers.get("Content-Type", "")

            text_preview = ""
            if "text" in content_type or "html" in content_type or "json" in content_type:
                try:
                    text_preview = response.text[:2000]
                except Exception:
                    text_preview = ""

            if (
                "Failed to verify your browser" in text_preview
                or "Code 705" in text_preview
                or "code 705" in text_preview.lower()
            ):
                return self._error(
                    502,
                    "RavenKoG blocked this server request with browser verification Code 705",
                    {
                        "blocked_by": "ravenkog",
                        "status_code": response.status_code,
                        "reason": (
                            "The proxy is working, but RavenKoG is rejecting "
                            "requests coming from the Vercel server."
                        ),
                    },
                )

            if not content_type:
                content_type = "application/octet-stream"

            self._send(
                response.status_code,
                response.content,
                content_type,
            )

        except requests.Timeout:
            self._error(
                504,
                "ravenkog.com timed out",
            )

        except requests.ConnectionError:
            self._error(
                502,
                "Could not reach ravenkog.com",
            )

        except Exception as exc:
            self._error(
                500,
                "Proxy crashed",
                {"details": str(exc)},
            )
