#!/bin/bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# /opt/mopidy-dev/ should already exist with eboback cloned during bootstrapping.

# dir tree will look like:
# /opt/mopidy-dev/
#     venv
#     mopidy
#     eboplayer
#     eboback

# fill the folders:
cd /opt/mopidy-dev  || exit
python3 -m venv --system-site-packages venv
git clone https://github.com/ErikBongers/mopidy.git
git clone https://github.com/ErikBongers/mopidy-eboplayer.git

# checkout correct branches
cd /opt/mopidy-dev/mopidy || exit
git checkout GstStructureNotNone

#install the pip packages
source /opt/mopidy-dev/venv/bin/activate
cd /opt/mopidy-dev/mopidy || exit
pip install .

cd /opt/mopidy-dev/mopidy-eboback || exit
# Required for eboback
sudo apt install -y libasound2-dev
pip install .

cd /opt/mopidy-dev/mopidy_eboplayer || exit
pip install .
