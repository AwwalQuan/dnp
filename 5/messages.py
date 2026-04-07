"""
Message types for P2P drone swarm: state and optional shared destination (waypoint).
All messages are JSON dicts, one line (newline-terminated).
"""

import json

def serialize(msg):
    return (json.dumps(msg) + "\n").encode("utf-8")

def deserialize(data):
    return json.loads(data.decode("utf-8").strip())

# --- Swarm P2P messages ---

def state_update(drone_id, x, y):
    """Broadcast my position to neighbors."""
    return {"type": "StateUpdate", "drone_id": drone_id, "x": x, "y": y}

def destination_update(destination_x, destination_y):
    """Share a common destination (waypoint) so the swarm moves there."""
    return {
        "type": "DestinationUpdate",
        "destination_x": destination_x,
        "destination_y": destination_y,
    }
