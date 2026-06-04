"""
Vercel Python Serverless Function
Proxies requests to www.ravenkog.com from the browser.

Deployed automatically by Vercel when pushed to GitHub.
Accessible at:  https://your-project.vercel.app/api/proxy?url=...
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote
import requests
import json

ALLOWED_HOST = "www.ravenkog.com"
TIMEOUT      = 9   # Vercel Hobby plan caps at 10 s — keep this under

FORWARD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         f"https://{ALLOWED_HOST}/",
}


class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default stdout logs on Vercel

    # ── helpers ───────────────────────────────────────────────────────────────

    def _send(self, code, body: bytes, mime="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, msg):
        self._send(code, json.dumps({"error": msg}).encode())

    # ── CORS preflight ────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self._send(200, b"")

    # ── Main handler ──────────────────────────────────────────────────────────

    def do_GET(self):
        # Parse ?url= from query string
        params = parse_qs(urlparse(self.path).query)
        url    = unquote(params.get("url", [""])[0]).strip()

        # Validate
        if not url:
            return self._error(400, "Missing ?url= parameter")

        if urlparse(url).netloc != ALLOWED_HOST:
            return self._error(403, f"Only {ALLOWED_HOST} URLs are allowed")

        # Forward to ravenkog.com
        try:
            resp  = requests.get(url, headers=FORWARD_HEADERS, timeout=TIMEOUT)
            ctype = resp.headers.get("Content-Type", "application/json")
            self._send(resp.status_code, resp.content, ctype)

        except requests.Timeout:
            self._error(504, "ravenkog.com timed out")

        except requests.ConnectionError:
            self._error(502, "Could not reach ravenkog.com")

        except Exception as exc:
            self._error(500, str(exc))
