#!/usr/bin/env python3
"""
Tutorial 6: Primary node (e.g. US).
Accepts password changes; replicates to replica after a delay.
"""
import json
import os
import threading
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from common import hash_password

REPLICATION_DELAY_SEC = int(os.environ.get("REPLICATION_DELAY_SEC", "180"))  # default 3 minutes
REPLICA_URL = os.environ.get("REPLICA_URL", "http://replica:5001")
PORT = int(os.environ.get("PORT", "5000"))


class PrimaryHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[primary] {format % args}")

    def do_POST(self):
        if self.path == "/change-password":
            self._change_password()
        elif self.path == "/login":
            self._login()
        else:
            self._send(404, {"error": "Not found"})

    def _change_password(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = json.loads(body)
            password = data.get("password")
            if not password:
                self._send(400, {"error": "missing password"})
                return
        except (json.JSONDecodeError, ValueError) as e:
            self._send(400, {"error": str(e)})
            return

        new_hash = hash_password(password)
        with self.server.state_lock:
            self.server.password_hash = new_hash

        print(f"[primary] Password updated (hash stored), replicating to replica in {REPLICATION_DELAY_SEC}s")
        self._send(200, {"status": "ok", "message": "Password updated"})

        # Replicate to replica after delay (async)
        def replicate_later():
            print(
                f"[primary] Replication thread started: will POST to replica "
                f"after {REPLICATION_DELAY_SEC}s"
            )
            time.sleep(REPLICATION_DELAY_SEC)
            print("[primary] Replication delay elapsed; sending password_hash to replica...")
            try:
                req = urllib.request.Request(
                    f"{REPLICA_URL}/replicate",
                    data=json.dumps({"password_hash": new_hash}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        print("[primary] Replication sent to replica successfully")
            except Exception as e:
                print(f"[primary] Replication failed: {e}")

        t = threading.Thread(target=replicate_later)
        t.daemon = True
        t.start()

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
    server = HTTPServer(("0.0.0.0", PORT), PrimaryHandler)
    server.password_hash = hash_password("old123")
    server.state_lock = threading.Lock()
    print(f"[primary] Listening on 0.0.0.0:{PORT} (replica URL: {REPLICA_URL})")
    server.serve_forever()


if __name__ == "__main__":
    main()
