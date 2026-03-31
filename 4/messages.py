"""
Message types for Raft-like leader election and heartbeats.
All messages are JSON dicts sent as one line (terminated by newline).
"""

import json

def serialize(msg):
    return (json.dumps(msg) + "\n").encode("utf-8")

def deserialize(data):
    return json.loads(data.decode("utf-8").strip())

# --- Raft protocol messages ---

def request_vote(term, candidate_id):
    return {"type": "RequestVote", "term": term, "candidate_id": candidate_id}

def request_vote_response(term, vote_granted, voter_id=None):
    return {"type": "RequestVoteResponse", "term": term, "vote_granted": vote_granted, "voter_id": voter_id}

def append_entries(term, leader_id):
    """Heartbeat: empty AppendEntries from leader."""
    return {"type": "AppendEntries", "term": term, "leader_id": leader_id}

def append_entries_response(term, success):
    return {"type": "AppendEntriesResponse", "term": term, "success": success}

# --- Client-facing (tasks for leader) ---

def get_leader_request():
    return {"type": "GetLeader"}

def get_leader_response(leader_id, term):
    return {"type": "GetLeaderResponse", "leader_id": leader_id, "term": term}

def submit_task_request(payload):
    return {"type": "SubmitTask", "payload": payload}

def submit_task_response(task_id, success, leader_id=None, assigned_node=None, result=None):
    return {
        "type": "SubmitTaskResponse",
        "task_id": task_id,
        "success": success,
        "leader_id": leader_id,
        "assigned_node": assigned_node,
        "result": result,
    }

def redirect_to_leader(leader_id):
    """Sent by follower when client asked for something only leader can do."""
    return {"type": "Redirect", "leader_id": leader_id}

# --- Leader -> worker: assign and execute task ---

def execute_task(task_id, payload):
    """Leader sends this to the node that should run the task."""
    return {"type": "ExecuteTask", "task_id": task_id, "payload": payload}

def execute_task_response(task_id, success, result=None):
    """Worker sends this back to the leader after executing the task."""
    return {"type": "ExecuteTaskResponse", "task_id": task_id, "success": success, "result": result}
