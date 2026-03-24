#!/bin/bash
# Cascading failure demo: many concurrent "users" hammering a slow endpoint with retries.
# Usage: ./cascade_client.sh [URL] [TIMEOUT] [RETRIES] [USERS] [REQ_PER_USER]
# Default URL: demo_server.py slow route (start server: python3 demo_server.py).
# Do NOT combine huge netem (e.g. 3000ms on lo) with short --max-time: curl may
# time out during TCP before GET reaches the server → no logs in demo_server.py.
# Retries here come from /slow?delay=5 vs default 2s timeout.
URL="${1:-http://127.0.0.1:8765/slow?delay=5}"
TIMEOUT="${2:-2}"
RETRIES="${3:-3}"
USERS="${4:-20}"
REQUESTS_PER_USER="${5:-5}"

echo "Cascade demo: $USERS users, $REQUESTS_PER_USER requests each, timeout=${TIMEOUT}s, retries=$RETRIES"
echo "URL: $URL"
echo "Start time: $(date -Iseconds)"

for u in $(seq 1 "$USERS"); do
  (
    for r in $(seq 1 "$REQUESTS_PER_USER"); do
      for i in $(seq 1 "$RETRIES"); do
        curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$URL" && break
        sleep 0.5
      done
    done
  ) &
done
wait
echo "End time: $(date -Iseconds)"
echo "All clients finished"
