#!/usr/bin/env python3
"""
Tutorial 6: Replica node (e.g. Europe).
Receives replication updates from primary; serves login checks (reads).
"""
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from common import hash_password

PORT = int(os.environ.get("PORT", "5001"))


class ReplicaHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[replica] {format % args}")

    def do_POST(self):
        if self.path == "/replicate":
            self._replicate()
        elif self.path == "/login":
            self._login()
        else:
            self._send(404, {"error": "Not found"})

    def _replicate(self):
        print("[replica] POST /replicate received from primary")
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = json.loads(body)
            new_hash = data.get("password_hash")
            if not new_hash:
                self._send(400, {"error": "missing password_hash"})
                return
        except (json.JSONDecodeError, ValueError) as e:
            self._send(400, {"error": str(e)})
            return

        with self.server.state_lock:
            self.server.password_hash = new_hash

        print("[replica] Replication applied: password_hash updated (new password active on replica)")
        self._send(200, {"status": "ok"})

    def _login(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = json.loads(body)
            password = data.get("password")
            if password is None:
                self._send(400, {"error": "missing password"})
                return
        except (json.JSONDecodeError, ValueError) as e:
            self._send(400, {"error": str(e)})
            return

        with self.server.state_lock:
            current_hash = self.server.password_hash

        ok = hash_password(password) == current_hash
        if ok:
            self._send(200, {"status": "ok", "login": "success"})
        else:
            self._send(401, {"status": "error", "login": "failure"})

    def _send(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def main():
    server = HTTPServer(("0.0.0.0", PORT), ReplicaHandler)
    server.password_hash = hash_password("old123")
    server.state_lock = threading.Lock()
    print(f"[replica] Listening on 0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
