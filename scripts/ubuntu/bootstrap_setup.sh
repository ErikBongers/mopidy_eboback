#!/bin/bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

mkdir -p /opt/mopidy-dev && cd /opt/mopidy-server || exit
# Give your user ownership so you can clone repositories and write code safely
REAL_USER="${SUDO_USER:-$(whoami)}"
chown -R $REAL_USER:$REAL_USER /opt/mopidy-dev

apt install git