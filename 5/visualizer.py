#!/usr/bin/env python3
"""
Real-time visualizer for the drone swarm. Run this first, then start the drones.
Drones push their (id, x, y) to this process; we plot positions in 2D and update at ~10 Hz.
Destination (waypoint) is shown as a red star (default 50, 50). Arena is [0, 100] x [0, 100].
"""

import socket
import threading
import time


def _init_plotting():
    """Pick a working interactive Matplotlib backend with clear errors."""
    import matplotlib

    backend_errors = []
    for backend in ("TkAgg", "QtAgg"):
        try:
            if backend == "TkAgg":
                # Ensure Tk + Pillow Tk bindings exist before selecting TkAgg.
                import tkinter  # noqa: F401
                from PIL import ImageTk  # noqa: F401
            matplotlib.use(backend, force=True)
            import matplotlib.pyplot as plt_local
            import matplotlib.animation as animation_local
            return plt_local, animation_local, backend
        except Exception as exc:
            backend_errors.append((backend, str(exc)))

    print("Could not initialize an interactive Matplotlib backend.")
    print("Tried backends: TkAgg, QtAgg")
    print("On Fedora, install GUI deps and retry:")
    print("  sudo dnf install -y python3-tkinter python3-pillow-tk")
    print("Then run: python3 visualizer.py")
    for backend, err in backend_errors:
        print(f"- {backend} failed: {err}")
    raise SystemExit(1)


plt, animation, SELECTED_BACKEND = _init_plotting()

from config import DRONES, INIT_CLUSTER_CENTER
from messages import deserialize

# Shared state: drone_id -> (x, y); destination waypoint (x, y)
positions = {}
destination = [50.0, 50.0]
lock = threading.Lock()

ARENA = (0, 100)


def run_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 11000))
    sock.listen(10)
    print("Visualizer listening on 127.0.0.1:11000 — start the drones now.")

    while True:
        conn, addr = sock.accept()
        t = threading.Thread(target=handle_conn, args=(conn,))
        t.daemon = True
        t.start()


def handle_conn(conn):
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
                with lock:
                    if msg.get("type") == "StateUpdate":
                        positions[msg["drone_id"]] = (msg["x"], msg["y"])
                    elif msg.get("type") == "DestinationUpdate":
                        destination[0] = msg["destination_x"]
                        destination[1] = msg["destination_y"]
    except Exception:
        pass
    finally:
        conn.close()


def animate(frame):
    with lock:
        state_items = sorted(positions.items(), key=lambda kv: kv[0])  # (drone_id, (x,y))
        tx, ty = destination[0], destination[1]
    ax.clear()
    ax.set_xlim(ARENA[0], ARENA[1])
    ax.set_ylim(ARENA[0], ARENA[1])
    ax.set_aspect("equal")
    ax.set_facecolor("#1a1a2e")
    ax.grid(True, alpha=0.3)

    if state_items:
        pts = [xy for _, xy in state_items]
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, c="cyan", s=120, edgecolors="white", linewidths=1.5, zorder=3)
        for drone_id, (px, py) in state_items:
            ax.annotate(str(drone_id), (px, py), color="white", fontsize=9, ha="center", va="center")

    ax.plot(tx, ty, marker="*", color="red", markersize=20, label="Destination", zorder=2)
    ax.legend(loc="upper right", facecolor="#16213e")

    # Telemetry panel: shows current destination and the latest broadcast state per drone.
    lines = [f"Destination: ({tx:.1f}, {ty:.1f})", "Broadcast state:"]
    if state_items:
        for drone_id, (px, py) in state_items:
            lines.append(f"  d{drone_id}: ({px:.1f}, {py:.1f})")
    else:
        lines.append("  (no updates yet)")
    panel_text = "\n".join(lines)
    ax.text(
        0.02, 0.98, panel_text,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        color="white",
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#16213e", edgecolor="white", alpha=0.9),
        zorder=5,
    )
    return []


if __name__ == "__main__":
    print(f"Visualizer backend: {SELECTED_BACKEND}")
    try:
        fig, ax = plt.subplots(figsize=(8, 8))
    except Exception as exc:
        print("Failed to open GUI window for visualizer.")
        print("Make sure you are running in a desktop session (X11/Wayland), not headless SSH.")
        print("If using SSH, enable X forwarding (ssh -X) or run locally.")
        print(f"Backend error: {exc}")
        raise SystemExit(1)
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.3)

    ani = animation.FuncAnimation(fig, animate, interval=100, blit=False, cache_frame_data=False)
    plt.title("Drone swarm — start near cluster, move to destination (red star), avoid collision")
    plt.tight_layout()
    plt.show()
