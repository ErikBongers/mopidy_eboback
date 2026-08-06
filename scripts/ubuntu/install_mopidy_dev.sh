#!/bin/bash

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# /opt/mopidy-dev/ should already exist with eboback cloned during bootstrapping.

# dir tree will look like:
# /opt/mopidy-dev/
#     venv
#     mopidy
#     eboplayer
#     eboback
#     TextScanner

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
git remote add upstream https://github.com/mopidy/mopidy.git
git fetch upstream --tags
pip install .

"$SCRIPT_DIR/install_text_scanner.sh"

cd /opt/mopidy-dev/mopidy_eboback || exit
# Required for eboback
sudo apt install -y libasound2-dev
pip install .

cd /opt/mopidy-dev/mopidy-eboplayer || exit
sudo mkdir -p /var/lib/eboplayer
sudo chmod 777 /var/lib/eboplayer
pip install .
