"""
DexMind — Dashboard Handler
Serves the dashboard HTML page.
"""

import os
from http.server import BaseHTTPRequestHandler

# Read HTML at import time (bundled with deployment)
_HERE = os.path.dirname(os.path.abspath(__file__))
_HTML_PATH = os.path.join(_HERE, "dashboard.html")

try:
    with open(_HTML_PATH, "rb") as f:
        DASHBOARD_HTML = f.read()
except FileNotFoundError:
    DASHBOARD_HTML = b"<h1>Dashboard not found</h1>"


class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(DASHBOARD_HTML)))
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML)
