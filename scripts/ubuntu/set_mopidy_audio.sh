#!/bin/bash

MOPIDY_AUDIO_OUTPUT=$1

# If no parameter was provided, prompt the user interactively
if [ -z "$MOPIDY_AUDIO_OUTPUT" ]; then
    # shellcheck disable=SC2162
    read -p "Enter the mopidy [audio.output] value: " MOPIDY_AUDIO_OUTPUT  < /dev/tty
fi

mkdir -p /opt/mopidy-dev/.config
# this creates the default config file, displays it on screen but does NOT start mopidy.
mopidy --config /opt/mopidy-dev/.config/mopidy.conf config
sudo chmod 777 /opt/mopidy-dev/.config/mopidy.conf

# change the config file
sed -i "/^#output = autoaudiosink$/c\output = $MOPIDY_AUDIO_OUTPUT" /opt/mopidy-dev/.config/mopidy.conf