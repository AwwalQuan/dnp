"""
Drone swarm configuration: list of (host, port) for each drone.
All drones must use the same config to know each other's addresses.
"""

# (host, port) for each drone. Use 127.0.0.1 and different ports for local testing.
DRONES = [
    ("127.0.0.1", 10001),
    ("127.0.0.1", 10002),
    ("127.0.0.1", 10003),
    ("127.0.0.1", 10004),
    ("127.0.0.1", 10005),
]

# Optional: (host, port) of the visualizer. If set, each drone pushes its position every step.
# Set to None to run without visualization.
VISUALIZER = ("127.0.0.1", 11000)

# Start positions: drones spawn near this point (random within radius) so they begin clustered.
INIT_CLUSTER_CENTER = (15.0, 15.0)
INIT_CLUSTER_RADIUS = 8.0

# --- Incremental security: reject state/destination updates from rogue devices ---
# If True, only messages signed with SWARM_SECRET are accepted (see swarm_auth.py).
# Default False keeps the original simulation unchanged.
SECURE_SWARM = False
# Shared secret (all legitimate drones and the command sender must use the same).
# In production use a strong secret from env or a key file.
SWARM_SECRET = b"swarm-secret-change-in-production"
