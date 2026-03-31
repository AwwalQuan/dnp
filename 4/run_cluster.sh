#!/bin/bash
# Start 3 nodes in the background. Stop with: pkill -f raft_node
cd "$(dirname "$0")"
python3 raft_node.py 0 &
python3 raft_node.py 1 &
python3 raft_node.py 2 &
echo "Cluster starting. Wait a few seconds, then: python3 client.py 127.0.0.1 9001 get-leader"
echo "To stop: pkill -f raft_node"
