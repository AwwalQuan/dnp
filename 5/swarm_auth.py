"""
Incremental security for the swarm: sign and verify messages so only devices
that share the swarm secret can have their state or destination (waypoint) updates
accepted. Rogue devices (without the secret) cannot inject fake ``StateUpdate`` or
``DestinationUpdate`` messages (see ``messages.destination_update``).
"""

import hmac
import hashlib
import json


def _payload_for_signature(msg):
    """Canonical form for signing: sort keys so same content => same signature."""
    return json.dumps(msg, sort_keys=True).encode("utf-8")


def sign_message(secret: bytes, msg: dict) -> dict:
    """Add a 'signature' field (HMAC-SHA256) to the message. Mutates and returns msg."""
    if "signature" in msg:
        del msg["signature"]
    payload = _payload_for_signature(msg)
    msg["signature"] = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return msg


def verify_message(secret: bytes, msg: dict) -> bool:
    """Return True if msg has a valid signature from a sender that knows secret."""
    sig = msg.get("signature")
    if not sig:
        return False
    msg_copy = dict(msg)
    del msg_copy["signature"]
    payload = _payload_for_signature(msg_copy)
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
