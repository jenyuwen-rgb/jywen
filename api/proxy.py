# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import json
import ssl

ALLOWED_HOST_SUFFIXES = (
    "kcsat.org", ".kcsat.org",
    "utk.com.tw", ".utk.com.tw",
    "tainanswim.com.tw", ".tainanswim.com.tw",
    "nowforyou.com", ".nowforyou.com",
    "tpesa.org.tw", ".tpesa.org.tw",
    "ntpc-sports.com", ".ntpc-sports.com",
    "hcc-swim.tw", ".hcc-swim.tw",
    "tyc-swim.tw", ".tyc-swim.tw",
    "storage.googleapis.com", ".googleapis.com",
    "github.io", ".github.io",
    "raw.githubusercontent.com",
    "vercel.app", ".vercel.app"
)

BLOCKED_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "::1")

def is_allowed_url(target_url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(target_url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower().strip()
        if not host or host in BLOCKED_HOSTS:
            return False
        if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
            return False
        return any(host == s or host.endswith(s if s.startswith(".") else "." + s) for s in ALLOWED_HOST_SUFFIXES)
    except Exception:
        return False

class handler(BaseHTTPRequestHandler):
    def _proxy_request(self, method, post_data=None):
        """Unified proxy logic for GET and POST with strict domain allowlist.
        Transparently forwards allowed official swimming association requests."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        url = params.get('url', [None])[0]

        if not url:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"error": "Missing url parameter"}')
            return

        if not is_allowed_url(url):
            self.send_response(403)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"error": "Forbidden: Destination host not in allowed swimming domains"}')
            return

        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        }
        if post_data is not None:
            req_headers['Content-Type'] = 'application/x-www-form-urlencoded'

        try:
            context = ssl._create_unverified_context()
            req = urllib.request.Request(url, data=post_data, headers=req_headers, method=method)
            with urllib.request.urlopen(req, timeout=20, context=context) as resp:
                body = resp.read()
                ct = resp.headers.get('Content-Type', 'text/html; charset=utf-8')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            err_body = json.dumps({'error': str(e)}, ensure_ascii=False).encode('utf-8')
            self.send_response(502)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)

    def do_GET(self):
        self._proxy_request('GET')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b''
        self._proxy_request('POST', post_data)
