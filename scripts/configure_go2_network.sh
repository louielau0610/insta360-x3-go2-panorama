#!/usr/bin/env bash
set -euo pipefail

INTERFACE="${1:?usage: $0 NETWORK_INTERFACE [HOST_IP] [ROBOT_IP]}"
HOST_IP="${2:-192.168.123.99}"
ROBOT_IP="${3:-192.168.123.161}"

if [[ ! -d "/sys/class/net/$INTERFACE" ]]; then
  echo "Network interface does not exist: $INTERFACE" >&2
  ip -brief link >&2
  exit 2
fi

sudo ip link set "$INTERFACE" up
sudo ip address replace "$HOST_IP/24" dev "$INTERFACE"
ip -brief address show dev "$INTERFACE"
ping -I "$INTERFACE" -c 3 -W 1 "$ROBOT_IP"
echo "GO2 network reachable on $INTERFACE"
