#!/bin/bash

# Setup pi
# ---------
# 1. Make and install image
#   > see AI help for: setup raspberry pi 4 headless via ethernet with ubuntu server
#   > see hostname and user below...
# 2. Open the user-data file on image and add section: (this makes ethernet mandatory and waits longer for it)
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
# 3. Boot and wait 5 minutes
#   > Login with ssh erik@eboaudioserver
# 4. Create or use ssh passwordless login key pair.
#   * On windows:
#       Get-Content "$HOME\.ssh\id_ed25519.pub" | ssh erik@eboaudioserver "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
#   * On android, in termux, create a key and copy it with
#       ssh-copy-id erik@eboaudioserver
#   - when all users have access (via passwordless ssh) disable password login.
#       todo: make this part of the setup, with a prompt yes/no?
#       sudo nano /etc/ssh/sshd_config.d/50-cloud-init.conf
# 5. Bootstrap this script (from the eboback repo.
#      curl -sSL https://raw.githubusercontent.com/ErikBongers/mopidy_eboback/refs/heads/master/scripts/ubuntu/bootstrap_setup.sh | bash
# 6. Then scan mopidy:
#      mopidy --config /opt/mopidy-dev/.config/mopidy.conf eboback scan
# 7. Start mopidy
#      mopidy --config /opt/mopidy-dev/.config/mopidy.conf

# This script must be called WITHOUT sudo privileges.
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

ENV_TYPE=$("$SCRIPT_DIR/detect_env.sh")

if [ "$ENV_TYPE" = "RP4" ]; then
   sudo "$SCRIPT_DIR/create_swap_file.sh"           # (in case of 1GB mem)
fi

sudo apt update
sudo apt upgrade
sudo apt install -y alsa-utils              # > installs aplay, amixer, alsamixer,...

if [ "$ENV_TYPE" = "RP4" ]; then
    sudo "$SCRIPT_DIR/fix_audio_cards_indices.sh"
    # Grant an ssh or headless user access to audio
    sudo usermod -a -G audio "$USER" #add user erik to audio group
    sudo usermod -a -G audio mopidy #add user mopidy to audio group
    sudo newgrp audio #apply the new audio group.
   # "$SCRIPT_DIR/set_default_soundcard.sh" 3  #set the soundcard to index 3 (usb)
fi

if [ "$ENV_TYPE" = "RP4" ]; then
    MOPIDY_AUDIO_OUTPUT="alsasink device=hw:3,0"
    MIXER="PCM"
    MEDIA_DIR=$(sudo "$SCRIPT_DIR/mount_media_usb.sh")
elif [ "$ENV_TYPE" = "WSL2" ]; then
    MOPIDY_AUDIO_OUTPUT="pulsesink"
    MIXER="Master"
    MEDIA_DIR="/mnt/d/Music/"
fi

"$SCRIPT_DIR/create_mopidy_config.sh" "$MOPIDY_AUDIO_OUTPUT" "$MEDIA_DIR" "$MIXER"
"$SCRIPT_DIR/install_mopidy_deps.sh"
"$SCRIPT_DIR/install_mopidy_dev.sh"
