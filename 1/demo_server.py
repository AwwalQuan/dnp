#!/usr/bin/env python3
"""Minimal HTTP server for Tutorial 1 netem/curl demos (127.0.0.1 only).

  GET /              -> 200 immediately
  GET /slow?delay=5  -> sleeps `delay` seconds (capped), then 200

Uses threads so many concurrent clients (cascade demo) can run.

Logs each request to stderr (incoming line, /slow sleep, response + timing).
"""
from __future__ import annotations

import http.server
import logging
import socketserver
import sys
import time
import urllib.parse

PORT = 8765
MAX_DELAY = 60.0

log = logging.getLogger("demo_server")


def _configure_logging() -> None:
    if log.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    log.addHandler(handler)
    log.setLevel(logging.INFO)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # Route stdlib http.server internal messages through our logger
        log.info(format % args)

    def do_GET(self) -> None:
        t0 = time.monotonic()
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        log.info("<< %s %s from %s", self.command, self.path, peer)

        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/slow":
            raw = qs.get("delay", ["5"])[0]
            try:
                requested = float(raw)
            except ValueError:
                requested = 5.0
                log.info("   bad delay=%r, using 5.0s", raw)
            delay = max(0.0, min(requested, MAX_DELAY))
            if requested != delay:
                log.info("   /slow sleep %.3fs (capped from %.3fs)", delay, requested)
            else:
                log.info("   /slow sleep %.3fs before 200", delay)
            time.sleep(delay)
        elif parsed.path != "/":
            ms = (time.monotonic() - t0) * 1000
            log.warning(">> 404 %s (%.1f ms)", self.path, ms)
            self.send_error(404, "Not Found")
            return

        body = b"ok\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        ms = (time.monotonic() - t0) * 1000
        log.info(">> 200 %s %d bytes (%.1f ms)", parsed.path or "/", len(body), ms)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    _configure_logging()
    log.info("Tutorial 1 demo server listening on http://127.0.0.1:%s/", PORT)
    log.info("Routes: GET /  |  GET /slow?delay=<seconds>  (logs go to stderr)")
    with ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
