import http.server
import socketserver
import os
import sys

PORT = 8089
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class DualStackServer(http.server.ThreadingHTTPServer):
    def server_bind(self):
        # Allow reuse address
        self.allow_reuse_address = True
        super().server_bind()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
        
    def end_headers(self):
        # Allow cross-origin and no cache for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

if __name__ == '__main__':
    with DualStackServer(('0.0.0.0', PORT), Handler) as httpd:
        print(f"Serving Annadel 3D Map on 0.0.0.0:{PORT}...")
        httpd.serve_forever()
