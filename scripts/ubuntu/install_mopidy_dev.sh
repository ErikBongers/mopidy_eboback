#!/bin/bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# dir tree will look like:
# /opt/mopidy-dev/
#     venv
#     mopidy
#     eboplayer
#     eboback

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

