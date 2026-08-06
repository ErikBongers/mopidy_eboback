#!/bin/bash

MOPIDY_AUDIO_OUTPUT=$1
MEDIA_DIR=$2
MIXER_NAME=$3

# If no parameter was provided, prompt the user interactively
if [ -z "$MOPIDY_AUDIO_OUTPUT" ]; then
    # shellcheck disable=SC2162
    echo ""
    read -p "Enter the mopidy [audio.output] value: " MOPIDY_AUDIO_OUTPUT  < /dev/tty
fi
if [ -z "$MEDIA_DIR" ]; then
    # shellcheck disable=SC2162
    echo ""
    read -p "Enter the mopidy [eboback.media_dir] value: " MEDIA_DIR  < /dev/tty
fi
if [ -z "$MIXER_NAME" ]; then
    # shellcheck disable=SC2162
    echo ""
    read -p "Enter the mopidy [eboback.alsa_mixer] value: " MIXER_NAME  < /dev/tty
fi

IP_ADDRESS=$(hostname -I | awk '{print $1}')

mkdir -p /opt/mopidy-dev/.config
# this creates the default config file, displays it on screen but does NOT start mopidy.
mopidy --config /opt/mopidy-dev/.config/mopidy.conf config
sudo chmod 777 /opt/mopidy-dev/.config/mopidy.conf

# change the config file
sed -i -e "/^#output = autoaudiosink$/c\output = $MOPIDY_AUDIO_OUTPUT" \
    -e "/^#media_dir = please_specify_a_media_dir_in_the_config_file$/c\media_dir = $MEDIA_DIR" \
    -e "/^#media_dirs =.*$/c\media_dirs = $MEDIA_DIR" \
    -e "/^#base_dir =   ; Unexpanded '$...' in path '.xdg_music_dir'$/c\base_dir = $MEDIA_DIR" \
    -e "/^#alsa_mixer = Master$/c\alsa_mixer = $MIXER_NAME" \
    -e "/^#hostname = 127.0.0.1.*$/c\hostname = $IP_ADDRESS" \
  /opt/mopidy-dev/.config/mopidy.conf
