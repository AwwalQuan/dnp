#!/usr/bin/env python3
"""
Minimal payment API demo.
- POST /pay: no idempotency; every request is processed (duplicate charges).
- POST /pay-idempotent: uses Idempotency-Key header; same key returns cached result, no duplicate charge.
- GET /stats: returns counts + balances (for demo inspection).
- GET /history: returns transaction history for both flows.

Python 3.6+ stdlib only. Run: python3 payment_server.py
"""

import json
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 8765

# In-memory state (reset on server restart)
INITIAL_BALANCE_RUB = 5000
charges_no_idempotency = 0
charges_idempotent = 0
idempotency_store = {}  # key -> {"payment_id", "status", "body"}
balance_no_idempotency = INITIAL_BALANCE_RUB
balance_idempotent = INITIAL_BALANCE_RUB
history_no_idempotency = []
history_idempotent = []
request_seq = 0


def parse_amount_rub(body):
    amount = body.get("amount_rub")
    if isinstance(amount, bool):
        return None
    if not isinstance(amount, int):
        return None
    if amount <= 0:
        return None
    return amount


class PaymentHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))

    def send_json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def read_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            return self.rfile.read(content_length).decode("utf-8", errors="replace")
        return "{}"

    def do_GET(self):
        if urlparse(self.path).path == "/stats":
            self.send_json(200, {
                "initial_balance_rub": INITIAL_BALANCE_RUB,
                "balance_no_idempotency_rub": balance_no_idempotency,
                "balance_idempotent_rub": balance_idempotent,
                "charges_no_idempotency": charges_no_idempotency,
                "charges_idempotent": charges_idempotent,
                "idempotency_keys_stored": len(idempotency_store),
            })
            return
        if urlparse(self.path).path == "/history":
            self.send_json(200, {
                "no_idempotency": history_no_idempotency,
                "idempotent": history_idempotent,
            })
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        global charges_no_idempotency, charges_idempotent
        global balance_no_idempotency, balance_idempotent
        global request_seq

        path = urlparse(self.path).path
        body_str = self.read_body()
        try:
            body = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON"})
            return
        amount_rub = parse_amount_rub(body)
        if amount_rub is None:
            self.send_json(400, {"error": "amount_rub must be a positive integer"})
            return

        if path == "/pay":
            request_seq += 1
            charges_no_idempotency += 1
            payment_id = "p-%s" % uuid.uuid4().hex[:12]
            balance_before = balance_no_idempotency
            balance_no_idempotency -= amount_rub
            result = {
                "payment_id": payment_id,
                "charged": True,
                "amount_rub": amount_rub,
                "balance_before_rub": balance_before,
                "balance_after_rub": balance_no_idempotency,
            }
            history_no_idempotency.append({
                "seq": request_seq,
                "path": "/pay",
                "amount_rub": amount_rub,
                "payment_id": payment_id,
                "charged": True,
                "balance_after_rub": balance_no_idempotency,
            })
            self.send_json(200, result)
            return

        if path == "/pay-idempotent":
            request_seq += 1
            key = self.headers.get("Idempotency-Key", "").strip()
            if not key:
                self.send_json(400, {"error": "Missing Idempotency-Key header"})
                return

            if key in idempotency_store:
                # Deduplication: return cached result, do not charge again
                stored = idempotency_store[key]
                history_idempotent.append({
                    "seq": request_seq,
                    "path": "/pay-idempotent",
                    "idempotency_key": key,
                    "amount_rub": amount_rub,
                    "payment_id": stored["body"]["payment_id"],
                    "charged": False,
                    "deduplicated": True,
                    "balance_after_rub": balance_idempotent,
                })
                response = dict(stored["body"])
                response["deduplicated"] = True
                self.send_json(stored["status"], response)
                return

            # First time for this key: execute and store
            charges_idempotent += 1
            payment_id = "p-%s" % uuid.uuid4().hex[:12]
            balance_before = balance_idempotent
            balance_idempotent -= amount_rub
            response_body = {
                "payment_id": payment_id,
                "charged": True,
                "amount_rub": amount_rub,
                "balance_before_rub": balance_before,
                "balance_after_rub": balance_idempotent,
                "deduplicated": False,
            }
            idempotency_store[key] = {"status": 200, "body": response_body}
            history_idempotent.append({
                "seq": request_seq,
                "path": "/pay-idempotent",
                "idempotency_key": key,
                "amount_rub": amount_rub,
                "payment_id": payment_id,
                "charged": True,
                "deduplicated": False,
                "balance_after_rub": balance_idempotent,
            })
            self.send_json(200, response_body)
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


def main():
    server = HTTPServer((HOST, PORT), PaymentHandler)
    print("Payment API demo listening on http://%s:%s" % (HOST, PORT))
    print("  POST /pay              — no idempotency (duplicate charges)")
    print("  POST /pay-idempotent   — Idempotency-Key header (deduplicated)")
    print("  GET  /stats            — balances + charge counts")
    print("  GET  /history          — transaction history")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
