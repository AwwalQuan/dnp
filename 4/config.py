"""
Cluster configuration: list of nodes (host, port) and derived quorum size.
All nodes must use the same config so they know each other's addresses.
"""

# (host, port) for each node. Use 127.0.0.1 and different ports for local testing.
NODES = [
    ("127.0.0.1", 9001),
    ("127.0.0.1", 9002),
    ("127.0.0.1", 9003),
]

def quorum_size():
    """Minimum number of nodes that must agree (majority)."""
    n = len(NODES)
    return (n // 2) + 1
