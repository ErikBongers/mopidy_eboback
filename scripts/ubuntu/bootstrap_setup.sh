#!/bin/bash

# bootstrap me with:
# curl -sSL https://raw.githubusercontent.com/ErikBongers/mopidy_eboback/refs/heads/master/scripts/ubuntu/bootstrap_setup.sh | bash

sudo mkdir -p /opt/mopidy-dev && cd /opt/mopidy-dev || exit
# Give your user ownership so you can clone repositories and write code safely
REAL_USER="${SUDO_USER:-$(whoami)}"
sudo chown -R $REAL_USER:$REAL_USER /opt/mopidy-dev

sudo apt install git

git clone https://github.com/ErikBongers/mopidy_eboback.git

cd /opt/mopidy-dev/mopidy_eboback/ || exit

sudo find scripts -type f -exec chmod +x {} +