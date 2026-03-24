#!/usr/bin/env python3
"""
Improved payment API demo — addresses pitfalls:
- Same key + different body → 409 Conflict (body fingerprint check).
- Key TTL (e.g. 24 h); expired keys are removed and request is treated as new.
- Adds account balances and transaction history so you can see deductions and deduped retries.

Python 3.6+ stdlib only. Run: python3 payment_server_improved.py
Listens on port 8766 (so you can run the original server on 8765 alongside).
"""

import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8766
TTL_SECONDS = 24 * 3600  # 24 hours

# In-memory state (reset on server restart)
charges_no_idempotency = 0
charges_idempotent = 0
INITIAL_BALANCE_RUB = 5000
balance_no_idempotency = INITIAL_BALANCE_RUB
balance_idempotent = INITIAL_BALANCE_RUB
idempotency_store = {}  # key -> {status, body, request_fingerprint, created_at}
history_no_idempotency = []
history_idempotent = []
request_seq = 0


def body_fingerprint(body):
    """Normalised fingerprint for request body (order-independent keys)."""
    return json.dumps(body, sort_keys=True)


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
            balance_before = balance_no_idempotency
            balance_no_idempotency -= amount_rub
            payment_id = "p-%s" % uuid.uuid4().hex[:12]
            history_no_idempotency.append({
                "seq": request_seq,
                "path": "/pay",
                "amount_rub": amount_rub,
                "payment_id": payment_id,
                "charged": True,
                "deduplicated": False,
                "balance_after_rub": balance_no_idempotency,
            })
            self.send_json(200, {
                "payment_id": payment_id,
                "charged": True,
                "amount_rub": amount_rub,
                "balance_before_rub": balance_before,
                "balance_after_rub": balance_no_idempotency,
                "deduplicated": False,
            })
            return

        if path == "/pay-idempotent":
            request_seq += 1
            key = self.headers.get("Idempotency-Key", "").strip()
            if not key:
                self.send_json(400, {"error": "Missing Idempotency-Key header"})
                return

            now = time.time()
            current_fingerprint = body_fingerprint(body)

            # Expire old entries (TTL)
            if key in idempotency_store:
                entry = idempotency_store[key]
                if now - entry["created_at"] > TTL_SECONDS:
                    del idempotency_store[key]

            if key in idempotency_store:
                stored = idempotency_store[key]
                if current_fingerprint != stored["request_fingerprint"]:
                    self.send_json(409, {
                        "error": "Idempotency key already used with a different request body",
                        "idempotency_key": key,
                    })
                    history_idempotent.append({
                        "seq": request_seq,
                        "path": "/pay-idempotent",
                        "idempotency_key": key,
                        "amount_rub": amount_rub,
                        "payment_id": stored["body"].get("payment_id"),
                        "charged": False,
                        "deduplicated": False,
                        "conflict": True,
                        "balance_after_rub": balance_idempotent,
                    })
                    return
                response = dict(stored["body"])
                response["deduplicated"] = True
                history_idempotent.append({
                    "seq": request_seq,
                    "path": "/pay-idempotent",
                    "idempotency_key": key,
                    "amount_rub": amount_rub,
                    "payment_id": response.get("payment_id"),
                    "charged": False,
                    "deduplicated": True,
                    "balance_after_rub": balance_idempotent,
                })
                self.send_json(stored["status"], response)
                return

            # First time for this key: execute and store (with fingerprint and TTL)
            charges_idempotent += 1
            balance_before = balance_idempotent
            payment_id = "p-%s" % uuid.uuid4().hex[:12]
            balance_idempotent -= amount_rub
            response_body = {
                "payment_id": payment_id,
                "charged": True,
                "amount_rub": amount_rub,
                "balance_before_rub": balance_before,
                "balance_after_rub": balance_idempotent,
                "deduplicated": False,
            }
            idempotency_store[key] = {
                "status": 200,
                "body": response_body,
                "request_fingerprint": current_fingerprint,
                "created_at": now,
            }
            self.send_json(200, response_body)
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
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


def main():
    server = HTTPServer((HOST, PORT), PaymentHandler)
    print("Payment API (improved) listening on http://%s:%s" % (HOST, PORT))
    print("  POST /pay              — no idempotency")
    print("  POST /pay-idempotent   — Idempotency-Key + body check (409 if mismatch) + TTL=%sh" % (TTL_SECONDS // 3600))
    print("  GET  /stats            — balances + charge counts")
    print("  GET  /history          — transaction history (ledger)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
