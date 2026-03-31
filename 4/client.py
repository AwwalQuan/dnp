#!/usr/bin/env python3
"""
Simple client to talk to the cluster: ask who is leader, submit a task.
Usage: python3 client.py <host> <port> [get-leader|submit <payload>]
Default: get-leader. Example: python3 client.py 127.0.0.1 9001 submit "hello"
"""

import sys
import socket
from messages import (
    serialize,
    deserialize,
    get_leader_request,
    submit_task_request,
)

def send(host, port, msg):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect((host, port))
    s.send(serialize(msg))
    buf = b""
    while b"\n" not in buf:
        buf += s.recv(4096)
        if not buf:
            break
    s.close()
    return deserialize(buf) if buf else None

def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9001
    cmd = sys.argv[3] if len(sys.argv) > 3 else "get-leader"
    payload = sys.argv[4] if len(sys.argv) > 4 else ""

    if cmd == "get-leader":
        resp = send(host, port, get_leader_request())
        if resp and resp.get("type") == "GetLeaderResponse":
            print(f"Leader: node {resp.get('leader_id')}, term {resp.get('term')}")
        elif resp and resp.get("type") == "Redirect":
            print(f"Redirect to leader: node {resp.get('leader_id')}")
        else:
            print("No leader or error:", resp)
    elif cmd == "submit":
        resp = send(host, port, submit_task_request(payload))
        if resp and resp.get("type") == "SubmitTaskResponse":
            if resp.get("success"):
                tid = resp.get("task_id")
                node = resp.get("assigned_node")
                result = resp.get("result")
                print(f"Task submitted: id={tid}" + (f", assigned to node {node}, result={result!r}" if node is not None else ""))
            else:
                print(f"Failed (not leader?). Leader: {resp.get('leader_id')}")
        elif resp and resp.get("type") == "Redirect":
            print(f"Redirect to leader node {resp.get('leader_id')} to submit task")
        else:
            print("Error:", resp)
    else:
        print("Usage: client.py <host> <port> [get-leader|submit <payload>]")

if __name__ == "__main__":
    main()
