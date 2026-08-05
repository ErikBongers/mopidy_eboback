#!/bin/bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# dir tree will look like:
# /opt/mopidy-dev/
#     venv
#     mopidy
#     eboplayer
#     eboback

#mkdir -p /home/erik/mopidy-server && cd /home/erik/mopidy-server
mkdir -p /opt/mopidy-dev && cd /opt/mopidy-server || exit
# Give your user ownership so you can clone repositories and write code safely
REAL_USER="${SUDO_USER:-$(whoami)}"
chown -R $REAL_USER:$REAL_USER /opt/mopidy-dev

python3 -m venv --system-site-packages venv

git clone ...whatever mopidy version
cd mopidy || exit
pip install .

# Install eboback
# ------------------
apt install -y libasound2-dev
git clone
cd eboback || exit
source ~/mopidy-server/venv/bin/activate
pip install .

"$SCRIPT_DIR/create_mopidy_user.sh"
"$SCRIPT_DIR/create_media_grp.sh"

