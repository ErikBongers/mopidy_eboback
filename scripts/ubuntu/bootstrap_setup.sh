#!/bin/bash

# bootstrap me with:
# curl -sSL https://raw.githubusercontent.com/ErikBongers/mopidy_eboback/refs/heads/master/scripts/ubuntu/bootstrap_setup.sh | sudo bash

mkdir -p /opt/mopidy-dev && cd /opt/mopidy-dev || exit
# Give your user ownership so you can clone repositories and write code safely
REAL_USER="${SUDO_USER:-$(whoami)}"
chown -R $REAL_USER:$REAL_USER /opt/mopidy-dev

apt install git

