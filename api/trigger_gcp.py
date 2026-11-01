# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import urllib.request
import json
import ssl

TRIGGER_URL = "https://swim-trigger-api-287296629155.asia-east1.run.app/?token=swim-super-secret-2026"

class handler(BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def do_POST(self):
        self._forward()

    def do_GET(self):
        self._forward()

    def _forward(self):
        try:
            req = urllib.request.Request(
                TRIGGER_URL,
                data=b'{}',
                headers={'Content-Type': 'application/json', 'User-Agent': 'SwimmingPWA-VercelProxy/1.0'}
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self._send_cors()
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._send_cors()
            self.end_headers()
            err_payload = json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False).encode('utf-8')
            self.wfile.write(err_payload)
