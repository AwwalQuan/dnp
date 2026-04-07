#!/usr/bin/env python3
"""
Send a shared destination (waypoint) to all drones so the swarm moves there.
Builds a ``DestinationUpdate`` message (see ``messages.destination_update``).
Usage: python3 send_destination.py <x> <y>   (default host 127.0.0.1; broadcasts to all)
Example: python3 send_destination.py 80 20
"""

import sys
import socket
from config import DRONES, VISUALIZER, SECURE_SWARM, SWARM_SECRET
from messages import serialize, destination_update
if SECURE_SWARM:
    from swarm_auth import sign_message

def main():
    tx = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0
    ty = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0

    msg = destination_update(tx, ty)
    if SECURE_SWARM:
        msg = sign_message(SWARM_SECRET, dict(msg))

    recipients = list(DRONES)
    if VISUALIZER:
        recipients.append(VISUALIZER)

    for (h, p) in recipients:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((h, p))
            s.send(serialize(msg))
            s.close()
        except Exception:
            pass
    print(f"Sent destination ({tx}, {ty}) to all drones" + (" (signed)" if SECURE_SWARM else ""))

if __name__ == "__main__":
    main()
