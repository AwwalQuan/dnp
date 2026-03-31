#!/usr/bin/env python3
"""
Minimal Raft-like cluster node: leader election and heartbeats (no log replication).
States: FOLLOWER, CANDIDATE, LEADER. Uses quorum for election; leader sends heartbeats.
"""

import hashlib
import json
import random
import socket
import threading
import time
from config import NODES, quorum_size
from messages import (
    serialize,
    deserialize,
    request_vote,
    request_vote_response,
    append_entries,
    append_entries_response,
    get_leader_request,
    get_leader_response,
    submit_task_request,
    submit_task_response,
    redirect_to_leader,
    execute_task,
    execute_task_response,
)

# Node states
FOLLOWER = "follower"
CANDIDATE = "candidate"
LEADER = "leader"


class RaftNode:
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.host, self.port = NODES[node_id]
        self.peers = [(h, p) for i, (h, p) in enumerate(NODES) if i != node_id]
        self.peer_node_ids = [i for i in range(len(NODES)) if i != node_id]
        self.quorum = quorum_size()

        self._lock = threading.Lock()
        self._state = FOLLOWER
        self._current_term = 0
        self._voted_for = None
        self._leader_id = None
        self._votes_received = set()
        self._last_heartbeat = time.time()
        self._task_counter = 0
        self._tasks = []
        self._executed_tasks = []

        self._election_timeout_min = 1.5
        self._election_timeout_max = 3.0
        self._heartbeat_interval = 0.4

    def _set_state(self, state, term=None, leader_id=None):
        with self._lock:
            self._state = state
            if term is not None:
                self._current_term = term
            if leader_id is not None:
                self._leader_id = leader_id
            if state == CANDIDATE:
                self._voted_for = self.node_id
                self._votes_received = {self.node_id}
            elif state == FOLLOWER:
                self._voted_for = None
                self._votes_received.clear()

    def _step_down_if_higher_term(self, term):
        with self._lock:
            if term > self._current_term:
                old_state = self._state
                old_term = self._current_term
                self._current_term = term
                self._state = FOLLOWER
                self._voted_for = None
                self._leader_id = None
                print(
                    f"[node {self.node_id}] saw higher term {term} "
                    f"(was term {old_term}, state={old_state}) -> FOLLOWER"
                )
                return True
        return False

    def _run_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(5)
        print(f"[node {self.node_id}] listening on {self.host}:{self.port}")

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
                    resp = self._dispatch(msg)
                    if resp:
                        conn.send(serialize(resp))
        except Exception as e:
            print(f"[node {self.node_id}] connection error: {e}")
        finally:
            conn.close()

    def _dispatch(self, msg):
        t = msg.get("type")
        if t == "RequestVote":
            return self._on_request_vote(msg)
        if t == "RequestVoteResponse":
            self._on_request_vote_response(msg)
            return None
        if t == "AppendEntries":
            return self._on_append_entries(msg)
        if t == "AppendEntriesResponse":
            self._on_append_entries_response(msg)
            return None
        if t == "GetLeader":
            return self._on_get_leader(msg)
        if t == "SubmitTask":
            return self._on_submit_task(msg)
        if t == "ExecuteTask":
            return self._on_execute_task(msg)
        return None

    def _on_request_vote(self, msg):
        term = msg["term"]
        candidate_id = msg["candidate_id"]
        self._step_down_if_higher_term(term)

        with self._lock:
            vote_granted = False
            if term >= self._current_term:
                if self._voted_for is None or self._voted_for == candidate_id:
                    self._voted_for = candidate_id
                    vote_granted = True
            print(
                f"[node {self.node_id}] vote request from node {candidate_id} "
                f"term={term} -> {'GRANT' if vote_granted else 'DENY'} "
                f"(current_term={self._current_term}, voted_for={self._voted_for})"
            )
            return request_vote_response(self._current_term, vote_granted, voter_id=self.node_id)

    def _on_request_vote_response(self, msg):
        term = msg["term"]
        vote_granted = msg["vote_granted"]
        self._step_down_if_higher_term(term)

        with self._lock:
            if self._state != CANDIDATE or term != self._current_term:
                return
            if vote_granted:
                self._votes_received.add(msg.get("voter_id", -1))
                print(
                    f"[node {self.node_id}] received vote in term {self._current_term}: "
                    f"{len(self._votes_received)}/{self.quorum}"
                )
                if len(self._votes_received) >= self.quorum:
                    self._state = LEADER
                    self._leader_id = self.node_id
                    self._voted_for = None
                    print(f"[node {self.node_id}] became LEADER for term {self._current_term}")
            else:
                print(
                    f"[node {self.node_id}] vote denied in term {self._current_term} "
                    f"by node {msg.get('voter_id')}"
                )

    def _on_append_entries(self, msg):
        term = msg["term"]
        leader_id = msg["leader_id"]
        self._step_down_if_higher_term(term)

        with self._lock:
            if term >= self._current_term:
                if self._leader_id is not None and self._leader_id != leader_id:
                    print(
                        f"[node {self.node_id}] leader changed "
                        f"{self._leader_id} -> {leader_id} (term {term})"
                    )
                elif self._leader_id is None:
                    print(
                        f"[node {self.node_id}] discovered leader node {leader_id} "
                        f"for term {term}"
                    )
                self._state = FOLLOWER
                self._leader_id = leader_id
                self._voted_for = None
                self._last_heartbeat = time.time()
            return append_entries_response(self._current_term, True)

    def _on_append_entries_response(self, msg):
        self._step_down_if_higher_term(msg["term"])

    def _on_get_leader(self, msg):
        with self._lock:
            if self._state == LEADER:
                return get_leader_response(self.node_id, self._current_term)
            if self._leader_id is not None:
                return redirect_to_leader(self._leader_id)
        return get_leader_response(None, self._current_term)

    def _on_submit_task(self, msg):
        with self._lock:
            if self._state != LEADER:
                if self._leader_id is not None:
                    return redirect_to_leader(self._leader_id)
                return submit_task_response(None, False, leader_id=None)

            self._task_counter += 1
            task_id = self._task_counter
            payload = msg.get("payload", "")
            self._tasks.append({"id": task_id, "payload": payload, "assigned_node": None, "result": None})

        # Assign to a worker (round-robin over peers)
        if not self.peer_node_ids:
            with self._lock:
                for t in self._tasks:
                    if t["id"] == task_id:
                        t["result"] = "no workers"
                        break
            return submit_task_response(task_id, True, assigned_node=None, result="no workers")

        peer_index = (task_id - 1) % len(self.peer_node_ids)
        target_node_id = self.peer_node_ids[peer_index]
        target_host, target_port = NODES[target_node_id]

        resp = self._send_to_peer(target_host, target_port, execute_task(task_id, payload))
        result = None
        if resp and resp.get("type") == "ExecuteTaskResponse" and resp.get("success"):
            result = resp.get("result")

        with self._lock:
            for t in self._tasks:
                if t["id"] == task_id:
                    t["assigned_node"] = target_node_id
                    t["result"] = result
                    break

        return submit_task_response(task_id, True, assigned_node=target_node_id, result=result)

    def _on_execute_task(self, msg):
        """Worker: run the task and return result. Simulates work (hash of payload)."""
        task_id = msg.get("task_id")
        payload = msg.get("payload", "")
        result = hashlib.sha256(payload.encode()).hexdigest()[:16]
        with self._lock:
            self._executed_tasks.append({"id": task_id, "payload": payload, "result": result})
        print(f"[node {self.node_id}] executed task {task_id}: payload={payload!r} -> result={result}")
        return execute_task_response(task_id, True, result=result)

    def _send_to_peer(self, host, port, msg):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((host, port))
            s.send(serialize(msg))
            buf = b""
            while b"\n" not in buf:
                buf += s.recv(4096)
                if not buf:
                    break
            if buf:
                return deserialize(buf)
            s.close()
        except Exception as e:
            pass
        return None

    def _request_votes(self):
        term = self._current_term
        print(f"[node {self.node_id}] requesting votes for term {term}")
        for (h, p) in self.peers:
            resp = self._send_to_peer(h, p, request_vote(term, self.node_id))
            if resp:
                self._dispatch(resp)

    def _send_heartbeats(self):
        term = self._current_term
        for (h, p) in self.peers:
            self._send_to_peer(h, p, append_entries(term, self.node_id))

    def run(self):
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()
        time.sleep(0.2)

        while True:
            with self._lock:
                state = self._state
                term = self._current_term
                last_hb = self._last_heartbeat

            if state == FOLLOWER:
                elapsed = time.time() - last_hb
                timeout = random.uniform(self._election_timeout_min, self._election_timeout_max)
                if elapsed >= timeout:
                    with self._lock:
                        known_leader = self._leader_id
                    if known_leader is not None:
                        print(
                            f"[node {self.node_id}] missed heartbeats from leader "
                            f"{known_leader} for {elapsed:.2f}s (timeout {timeout:.2f}s) "
                            "-> assuming leader failed"
                        )
                    else:
                        print(
                            f"[node {self.node_id}] no leader heartbeat for {elapsed:.2f}s "
                            f"(timeout {timeout:.2f}s)"
                        )
                    self._set_state(CANDIDATE, term=term + 1)
                    print(f"[node {self.node_id}] election timeout -> CANDIDATE term {self._current_term}")
                    self._request_votes()

            elif state == CANDIDATE:
                time.sleep(0.1)
                should_request_votes = False
                with self._lock:
                    if self._state != LEADER:
                        should_request_votes = True
                if should_request_votes:
                    # Never request votes while holding _lock; response dispatch
                    # paths also acquire _lock and can deadlock this thread.
                    self._request_votes()

            elif state == LEADER:
                self._send_heartbeats()
                time.sleep(self._heartbeat_interval)

            time.sleep(0.05)


def main():
    import sys
    node_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    n = RaftNode(node_id)
    n.run()


if __name__ == "__main__":
    main()
