#!/bin/bash

MOPIDY_AUDIO_OUTPUT=$1

# If no parameter was provided, prompt the user interactively
if [ -z "$MOPIDY_AUDIO_OUTPUT" ]; then
    # shellcheck disable=SC2162
    read -p "Enter the mopidy [audio.output] value: " MOPIDY_AUDIO_OUTPUT  < /dev/tty
fi

mkdir /opt/mopidy-def/.config
cat  << 'EOF' > /opt/mopidy-dev/.config/mopidy/mopidy.conf
[audio]
output=$MOPIDY_AUDIO_OUTPUT
EOF
sudo chmod 777 /opt/mopidy-dev/.config/mopidy/mopidy.conf