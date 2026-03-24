#!/bin/bash
# Retry demo: call a URL with retries. Use with a failing or slow endpoint.
# Usage: ./retry_demo.sh [URL] [MAX_RETRIES] [TIMEOUT_SEC]
# Default URL is fast GET / on demo_server.py (start: python3 demo_server.py).
# For retry amplification with visible server logs, use /slow?delay=3 with
# timeout 2 — not huge netem (handshake may never finish before curl quits).
set -e
URL="${1:-http://127.0.0.1:8765/}"
MAX_RETRIES="${2:-5}"
TIMEOUT="${3:-2}"

for i in $(seq 1 "$MAX_RETRIES"); do
  echo "Attempt $i/$MAX_RETRIES (timeout=${TIMEOUT}s)..."
  if curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$URL" | grep -q 200; then
    echo "Success on attempt $i"
    exit 0
  fi
  echo "Failed or timeout; waiting 1s before retry..."
  sleep 1
done
echo "All retries exhausted"
exit 1
