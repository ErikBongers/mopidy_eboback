#!/bin/bash

# Setup pi
# ---------
# * Make and install image
#   > see AI help for: setup raspberry pi 4 headless via ethernet with ubuntu server
#   > see hostname and user below...
# Open the user-data file on image and add section
#               write_files:
#                 - path: /etc/netplan/99-ethernet-wait.yaml
#                   permissions: '0600'
#                   content: |
#                     network:
#                       version: 2
#                       ethernets:
#                         eth0:
#                           dhcp4: true
#                           optional: false
# Boot and wait 5 minutes
#Login with ssh erik@eboaudioserver


# Create or use ssh passwordless login key pair.
# On windows:
# Get-Content "$HOME\.ssh\id_ed25519.pub" | ssh erik@eboaudioserver "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
# On android, in termux, create a key and copy it with
# ssh-copy-id erik@eboaudioserver
# when all users have access (via passwordless ssh) disable password login.
# sudo nano /etc/ssh/sshd_config.d/50-cloud-init.conf

# Now bootstrap this script (from the eboback repo. See instructions in bootstrap_setup.sh


# This script must be called WITHOUT sudo privileges.
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

ENV_TYPE=$("$SCRIPT_DIR/detect_env.sh")        # Get the environment ("RP4" or "WSL2")

if [ "$ENV_TYPE" = "RP4" ]; then
   sudo "$SCRIPT_DIR/create_swap_file.sh"           # Create swap file (in case of 1GB mem) and update the system
fi

sudo apt update
sudo apt upgrade

sudo apt install -y alsa-utils              # > installs aplay, amixer, alsamixer,...

# Enable the Pi's Onboard Audio Drivers (in a headless setup)
# ------------------------------------------------------------
if [ "$ENV_TYPE" = "RP4" ]; then
   "$SCRIPT_DIR/fix_audio_cards_indices.sh"
    # Grant an ssh or headless user access to audio
    sudo usermod -a -G audio "$ORIGINAL_USER" #add user erik to audio group
    sudo usermod -a -G audio mopidy #add user mopidy to audio group
    sudo newgrp audio #apply the new audio group.
   # "$SCRIPT_DIR/set_default_soundcard.sh" 3  #set the soundcard to index 3 (usb)
fi

#If this works, set the sink in mopidy:
if [ "$ENV_TYPE" = "RP4" ]; then
    MOPIDY_AUDIO_OUTPUT="alsasink device=hw:3,0"
    # MOPIDY_AUDIO_OUTPUT=alsasink
elif [ "$ENV_TYPE" = "WSL2" ]; then
    MOPIDY_AUDIO_OUTPUT="pulsesink"
fi

"$SCRIPT_DIR/mount_media_usb.sh"

"$SCRIPT_DIR/set_mopidy_audio" "$MOPIDY_AUDIO_OUTPUT"

"$SCRIPT_DIR/install_mopidy_deps.sh"

"$SCRIPT_DIR/install_mopidy_dev.sh"

Mount USB drive permanently (with removal)
-------------------------------------------------

Create text_scanner lib file
----------------------------------
(in venv)
git clone https://github.com/ErikBongers/TextScanner.git
apt  install rustup
rustup default stable
pip install maturin
cd text_scanner_py
maturin develop
> This should install the lib as a dep in the venv.

Setup for eboplayer
--------------------
mkdir -p /var/lib/eboplayer
chmod 777 /var/lib/eboplayer


# Fix internal soundcards to index 0, 1, 2 (and usb to 3)
-----------------------------------------------------------
