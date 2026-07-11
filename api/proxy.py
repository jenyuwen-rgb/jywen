from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import json

class handler(BaseHTTPRequestHandler):
    def _proxy_request(self, method, post_data=None):
        """Unified proxy logic for GET and POST. Transparently forwards
        the request and returns the remote response verbatim, preserving
        Content-Type so the browser can decide how to parse it."""
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

        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        }
        if post_data is not None:
            req_headers['Content-Type'] = 'application/x-www-form-urlencoded'

        import ssl
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
