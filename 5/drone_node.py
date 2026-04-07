#!/usr/bin/env python3
"""
Minimal P2P drone swarm: each drone shares its position with peers (gossip)
and moves toward the centroid of neighbors (cohesion / flocking).
No central leader — coordination is emergent from local rules.
"""

import math
import random
import socket
import threading
import time
from config import (
    DRONES,
    VISUALIZER,
    INIT_CLUSTER_CENTER,
    INIT_CLUSTER_RADIUS,
    SECURE_SWARM,
    SWARM_SECRET,
)
from messages import serialize, deserialize, state_update
if SECURE_SWARM:
    from swarm_auth import sign_message, verify_message


class DroneNode:
    def __init__(self, drone_id: int):
        self.drone_id = drone_id
        self.host, self.port = DRONES[drone_id]
        self.peers = [(h, p) for i, (h, p) in enumerate(DRONES) if i != drone_id]

        cx, cy = INIT_CLUSTER_CENTER
        r = INIT_CLUSTER_RADIUS
        self._lock = threading.Lock()
        self._x = cx + random.uniform(-r, r)
        self._y = cy + random.uniform(-r, r)
        self._destination_x = 50.0
        self._destination_y = 50.0
        self._peer_states = {}
        self._step = 0

        self._speed = 2.0
        self._gossip_interval = 0.2
        self._arena_size = 100.0
        self._separation_dist = 12.0
        self._separation_weight = 3.0
        self._visualizer = VISUALIZER

    def _run_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(5)
        print(f"[drone {self.drone_id}] listening on {self.host}:{self.port}")

        while True:
            conn, addr = sock.accept()
            t = threading.Thread(target=self._handle_connection, args=(conn,))
            t.daemon = True
            t.start()

    def _handle_connection(self, conn):
        try:
            buf = b""
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    msg = deserialize(line)
                    self._on_message(msg)
        except Exception as e:
            pass
        finally:
            conn.close()

    def _on_message(self, msg):
        if SECURE_SWARM and not verify_message(SWARM_SECRET, msg):
            return
        t = msg.get("type")
        if t == "StateUpdate":
            with self._lock:
                self._peer_states[msg["drone_id"]] = (msg["x"], msg["y"])
        elif t == "DestinationUpdate":
            with self._lock:
                self._destination_x = msg["destination_x"]
                self._destination_y = msg["destination_y"]

    def _send_to_peer(self, host, port, msg):
        if SECURE_SWARM and msg.get("type") in ("StateUpdate", "DestinationUpdate"):
            msg = dict(sign_message(SWARM_SECRET, dict(msg)))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((host, port))
            s.send(serialize(msg))
            s.close()
        except Exception:
            pass

    def _push_to_visualizer(self):
        if not self._visualizer:
            return
        with self._lock:
            x, y = self._x, self._y
        try:
            self._send_to_peer(
                self._visualizer[0], self._visualizer[1],
                state_update(self.drone_id, x, y),
            )
        except Exception:
            pass

    def _gossip_state(self):
        with self._lock:
            x, y = self._x, self._y
        for (h, p) in self.peers:
            self._send_to_peer(h, p, state_update(self.drone_id, x, y))

    def _compute_step(self):
        """Flocking: cohesion (centroid) + destination + separation (avoid collision using shared neighbor positions)."""
        with self._lock:
            x, y = self._x, self._y
            peers = dict(self._peer_states)
            tx, ty = self._destination_x, self._destination_y

        # Cohesion: toward centroid of neighbors (from shared state)
        if not peers:
            cx, cy = x, y
        else:
            cx = sum(p[0] for p in peers.values()) / len(peers)
            cy = sum(p[1] for p in peers.values()) / len(peers)

        blend = 0.6
        ax = blend * cx + (1 - blend) * tx - x
        ay = blend * cy + (1 - blend) * ty - y

        # Separation: steer away from neighbors that are too close (collision avoidance from shared info)
        sep_x, sep_y = 0.0, 0.0
        for (nx, ny) in peers.values():
            d = math.hypot(nx - x, ny - y)
            if 0.1 < d < self._separation_dist:
                away = self._separation_dist - d
                ux = (x - nx) / d
                uy = (y - ny) / d
                sep_x += ux * away
                sep_y += uy * away
        ax += self._separation_weight * sep_x
        ay += self._separation_weight * sep_y

        dist = math.hypot(ax, ay)
        if dist > 1e-6:
            ax /= dist
            ay /= dist
        dx = ax * self._speed
        dy = ay * self._speed

        with self._lock:
            self._x = max(0, min(self._arena_size, self._x + dx))
            self._y = max(0, min(self._arena_size, self._y + dy))
            self._step += 1

    def run(self):
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()
        time.sleep(0.2)

        while True:
            self._gossip_state()
            self._compute_step()
            self._push_to_visualizer()
            with self._lock:
                x, y = self._x, self._y
                step = self._step
            print(f"[drone {self.drone_id}] step {step}: pos=({x:.1f}, {y:.1f})")
            time.sleep(self._gossip_interval)


def main():
    import sys
    drone_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    node = DroneNode(drone_id)
    node.run()


if __name__ == "__main__":
    main()
