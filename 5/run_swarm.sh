#!/bin/bash
# Start 5 drones in the background. Stop with: pkill -f drone_node
cd "$(dirname "$0")"
for i in 0 1 2 3 4; do
  python3 drone_node.py $i &
done
echo "Swarm starting (5 drones). They start clustered, move to target, avoid collision."
echo "Optional: python3 visualizer.py  (in another terminal) to visualize in 2D."
echo "Optional: python3 send_destination.py 80 20  (move swarm to waypoint 80,20)"
echo "To stop: pkill -f drone_node"
